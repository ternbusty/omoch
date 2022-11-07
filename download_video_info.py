import requests
import datetime
from time import sleep
import subprocess
import csv
import os


class VideoInfo():
    def __init__(self, video_id, title, description, published_at, thumbnail_url) -> None:
        self.video_id = video_id
        self.title = title
        self.description = description
        self.published_at = published_at
        self.thumbnail_url = thumbnail_url

    def format(self) -> str:
        row = [self.video_id, self.title, self.description, self.published_at, self.thumbnail_url]
        return '\t'.join(row)


class YouTubeScraper():
    def __init__(self, playlist_id: str) -> None:
        self.log_file_path: str = 'log.tsv'
        self.API_KEY: str = os.environ['YOUTUBE_KEY']
        self.endpoint: str = 'https://www.googleapis.com/youtube/v3/'
        self.playlist_id: str = playlist_id
        self.video_info: VideoInfo = None
        self.comment_store: str = ''
        self.add_row_str_list: list[str] = []
        self.idx = 0
        self.load_tsv()

    def str_to_dt(self, dt_str: str) -> datetime.datetime:
        """
        Receives string like '%Y-%m-%dT%H:%M:%SZ' to `datetime` objects
        """
        return datetime.datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%SZ')

    def is_within_one_week_from_video_publish(self, target_dt: datetime.datetime) -> bool:
        """
        Return True when the target date is within one week from the video publish date
        """
        if target_dt <= self.published_at_dt + datetime.timedelta(days=7):
            return True
        else:
            return False

    def download_thumbnail(self) -> None:
        """
        Downlowd thumbnail of the video in the `self.video_info`
        """
        response: requests.Response = requests.get(self.video_info.thumbnail_url)
        image = response.content
        with open(f'./thumbnails/{self.video_info.video_id}.jpg', "wb") as f:
            f.write(image)

    def load_tsv(self) -> None:
        """
        Load a tsv file named "log.tsv" to `row_list`
        Save the latest video id in the log file to `last_row_id`
        """
        try:
            with open(self.log_file_path, encoding='utf-8') as f:
                reader = csv.reader(f, delimiter='\t')
                row_list: list[list[str]] = [row for row in reader]
                self.last_row_id: str = row_list[-1][0]
        except BaseException:  # If no such file exists
            first_row: str = '\t'.join(['video_id', 'title', 'description', 'published_at', 'thumbnail_url'])
            self.add_row_str_list.append(first_row)
            self.last_row_id: str = None

    def process_video_info(self, item: dict) -> None:
        """
        Take the `dict` of an item and
        - make `video_info` object
        - append the info to the `add_row_str_list`
        """
        snippet: dict = item['snippet']
        video_id: str = snippet['resourceId']['videoId']
        title: str = snippet['title']
        description: str = snippet['description'].translate(str.maketrans({'\r': ' ', '\n': ' '}))
        published_at: str = snippet['publishedAt']
        self.published_at_dt = self.str_to_dt(published_at)
        thumbnail_url: str = snippet['thumbnails']['medium']['url']
        print(self.idx, video_id, title)
        self.video_info = VideoInfo(video_id, title, description, published_at, thumbnail_url)

    def get_comments_from_snippet(self, snippet: dict) -> None:
        """
        Receives a dict of a comment and update `comment_store` with a formatted comment
        """
        dt_str: str = snippet['topLevelComment']['snippet']['publishedAt']
        # If the comment was written more than one week after the video publish date, skip
        if not self.is_within_one_week_from_video_publish(self.str_to_dt(dt_str)):
            return
        text: str = snippet['topLevelComment']['snippet']['textDisplay']
        text = text.translate(str.maketrans({'\r': ' ', '\n': ' '}))
        self.comment_store += f'{text}\n'

    def get_video_reply(self, next_page_token: str, parent_id: str) -> None:
        """
        Get replies of a comments specified by `parent_id` in the video
        in the `self.video_info` and save it to `self.comment_store`
        If nextPageToken exists, run this function recursively
        """
        sleep(1)
        params: dict = {
            'key': self.API_KEY,
            'part': 'snippet',
            'videoId': self.video_info.video_id,
            'textFormat': 'plaintext',
            'maxResults': 50,
            'parentId': parent_id,
        }
        if next_page_token is not None:
            params['pageToken'] = next_page_token
        response: requests.Response = requests.get(self.endpoint + 'comments', params=params)
        resource: dict = response.json()
        for comment_info in resource['items']:
            dt_str: str = comment_info['snippet']['publishedAt']
            if not self.is_within_one_week_from_video_publish(self.str_to_dt(dt_str)):
                continue
            text: str = comment_info['snippet']['textDisplay']
            text: str = text.translate(str.maketrans({'\r': ' ', '\n': ' '}))
            self.comment_store += f'{text}\n'
        if 'nextPageToken' in resource:
            self.get_video_reply(resource["nextPageToken"], parent_id)

    def get_video_comment(self, next_page_token: str) -> None:
        """
        Get comments of the video in the `self.video_info` and save it to `self.comment_store`
        - If there is a reply to a comment, exec `get_video_reply`
        - If nextPageToken exists, run this function recursively
        """
        sleep(1)
        params: dict[str, str] = {
            'key': self.API_KEY,
            'part': 'snippet',
            'videoId': self.video_info.video_id,
            'order': 'relevance',
            'textFormat': 'plaintext',
            'maxResults': 100,
        }
        if next_page_token is not None:
            params['pageToken'] = next_page_token
        response: requests.Response = requests.get(self.endpoint + 'commentThreads', params=params)
        resource: dict = response.json()
        for comment_info in resource['items']:
            snippet: dict = comment_info['snippet']
            dt_str: str = snippet['topLevelComment']['snippet']['publishedAt']
            # If the comment was written more than one week after the video publish date, skip
            if not self.is_within_one_week_from_video_publish(self.str_to_dt(dt_str)):
                continue
            text: str = snippet['topLevelComment']['snippet']['textDisplay']
            text = text.translate(str.maketrans({'\r': ' ', '\n': ' '}))
            self.comment_store += f'{text}\n'
            reply_cnt: int = snippet['totalReplyCount']
            parentId: str = snippet['topLevelComment']['id']
            if reply_cnt > 0:  # If a reply to the comment exists
                self.get_video_reply(None, parentId)  # Call "get_video_reply" with the parent id
        if 'nextPageToken' in resource:
            self.get_video_comment(resource['nextPageToken'])

    def process_comment(self) -> None:
        """
        Get comments of the video in the `self.video_info` and save to markdown file
        """
        self.comment_store: str = "---\nlayout: post\n" + \
            f"title: {self.video_info.title}\n" + \
            f"date: {self.video_info.published_at.split('T')[0]} 09:00:00 +0900\n" + \
            f"video_id: {self.video_info.video_id}\n" + \
            f"url: https://www.youtube.com/watch?v={self.video_info.video_id}\n---\n\n"
        # Collect comments
        self.get_video_comment(None)
        # Save comments to markdown file
        with open(f'./comments/{self.video_info.video_id}.md', mode='w', encoding='utf-8') as f:
            f.write(self.comment_store)

    def register_to_wp(self) -> None:
        """
        Register a comment file to wordpress
        """
        dt_str = self.video_info.published_at.split('T')[0]
        # dt_str = f"{self.video_info.published_at.split('T')[0]} 09:00:00 +0900\n"
        subprocess.run(['bash', 'register.sh', self.video_info.video_id, self.video_info.title, dt_str])

    def process(self, next_page_token=None) -> None:
        """
        Get videos from a playlist specified by `self.playlist_id`
        If next_page_token exist, call this function recursively
        """
        sleep(1)
        params: dict[str, str] = {
            'playlistId': self.playlist_id,
            'key': self.API_KEY,
            'part': 'snippet',
            'maxResults': 50,
        }
        if next_page_token is not None:
            params['pageToken']: str = next_page_token
        response: requests.Response = requests.get(self.endpoint + 'playlistItems', params=params)
        resource: dict = response.json()
        items: dict = resource['items']
        for item in items:
            self.idx += 1
            # Update `self.video_info`
            self.process_video_info(item)
            # If the video is already processed, exit
            if item['snippet']['resourceId']['videoId'] == self.last_row_id:
                return
            # If the video is published within one week, exit
            if self.is_within_one_week_from_video_publish(datetime.datetime.now()):
                continue
            self.add_row_str_list.append(self.video_info.format())
            # Get comments and update `self.comments`
            self.process_comment()
            self.download_thumbnail()
            self.register_to_wp()
        # If 'nextPageToken' is provided, call self.process() recursively
        if ('nextPageToken' in resource.keys()) and (resource['nextPageToken'] is not None):
            sleep(1)
            self.process(resource['nextPageToken'])

    def save_to_tsv(self) -> None:
        if len(self.add_row_str_list) == 0:
            return
        append_str: str = ''
        for row in reversed(self.add_row_str_list):
            append_str += row + '\n'
        with open(self.log_file_path, mode='a', encoding='utf8', newline='') as f:
            f.write(append_str)


if __name__ == '__main__':
    playlist_id: str = 'UUOx-oLP9tOhiYwSK_m-yVxA'
    yts = YouTubeScraper(playlist_id)
    yts.process()
    yts.save_to_tsv()
