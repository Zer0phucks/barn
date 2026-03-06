source /home/noob/barnhousing/.env
USER_ID="442fd9bb-5471-491c-b82d-7926407d935a"   # nsnfrd768@gmail.com

read -s -p "New password: " NEW_PASS; echo
curl -sS -X PUT "$SUPABASE_URL/auth/v1/admin/users/$USER_ID" \
  -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"Oaktown88**\",\"email_confirm\":true}" | jq '{id,email,email_confirmed_at}'
