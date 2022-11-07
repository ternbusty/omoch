ID=$1
POST_TITLE=$2
DT=$3
PATH="./comments/${ID}.md"
echo $PATH
POST_ID=`/usr/local/bin/wp post create ${PATH} --path="./www/" --post_title=${ID} --post_date=${DT} --post_status=publish --post_excerpt=${ID} --porcelain`
echo $POST_ID
/usr/local/bin/wp post update ${POST_ID} --path="./www/" --post_title="${POST_TITLE}"
/usr/local/bin/wp media import ./thumbnails/${ID}.jpg --path='./www/' --post_id=${POST_ID} --featured_image
