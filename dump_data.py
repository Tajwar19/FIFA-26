import json
from app import app

print("Dumping Flask API data to data.json...")
with app.test_client() as client:
    response = client.get('/api/data')
    if response.status_code == 200:
        data = response.get_json()
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("data.json updated successfully!")
    else:
        print(f"Failed to fetch data: {response.status_code}")
        print(response.data)
