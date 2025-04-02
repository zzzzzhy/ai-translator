export OPENAI_API_KEY=your_openai_api_key
python start.py

127.0.0.1:8005/docs


curl -X 'POST' \
  'http://127.0.0.1:8005/translate' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "data": [
    {
      "content": "尖椒炒肉",
      "lang": "zh"
    },
    {
      "content": "订单ID",
      "lang": "zh"
    }
  ]
}'