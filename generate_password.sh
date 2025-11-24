AUTH_LINE=$(grep -i "^AuthUserFile" .htaccess)
FILE_PATH=$(echo "$AUTH_LINE" | awk '{print $2}')
USER_NAME=$(echo "$FILE_PATH" | awk -F'/' '{print $3}')

#htpasswd -c /home/username/example.com/.htpasswd user1
NEW_CMD="htpasswd -c $FILE_PATH $USER_NAME"
echo $NEW_CMD
$(echo $NEW_CMD)

