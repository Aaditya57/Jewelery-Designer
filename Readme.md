"modelId": "5c232a9e-9061-4777-980a-ddc8e65647c6",
"photoReal": true,
"photoRealVersion": "v2",
"alchemy": false
Or if you want better quality via Alchemy v2, pair it with a compatible SDXL model:

json
Copy
Edit
"modelId": "5c232a9e-9061-4777-980a-ddc8e65647c6",
"photoReal": true,
"photoRealVersion": "v2",
"alchemy": true


dcfa3019610f221c8afe5691ddd85dd9eb69db43bdfa1ec0cc24a5cc81dee2e5



docker build . -t jewelry-design-app
docker-compose up jewelry-design-app -d
