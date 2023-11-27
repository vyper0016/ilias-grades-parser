import requests
import json
import concurrent.futures

def fetch_user(user:str):
    url = "https://rocketchat.hhu.de/api/v1/method.call/spotlight"
    headers = {
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "sec-ch-ua": "\"Chromium\";v=\"118\", \"Opera GX\";v=\"104\", \"Not=A?Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-auth-token": "o76dWE0IoKKjnwtCd7WOor9f1fbRh-gSuvE2OKIE11A",
        "x-user-id": "TBJJ3rQJc5bQRDygB",
    }

    body = {
        "message": '{"msg":"method",\
        "id":"22",\
        "method":"spotlight",\
        "params":' + f'\
            ["{user}",["{user}"]'
            + ',{"users":true,"rooms":true,"includeFederatedRooms":true}]\
        }'
    }

    response = requests.post(url, headers=headers, json=body, params=None, cookies=None)

    return response

def send_directory_request(count=100, offset=0):
    url = "https://rocketchat.hhu.de/api/v1/directory"
    params = {
        "count": count,
        "offset": offset,
        "query": '{"type":"users","text":"","workspace":"local"}',
        "sort": '{"name":1}',
    }

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "sec-ch-ua": "\"Chromium\";v=\"118\", \"Opera GX\";v=\"104\", \"Not=A?Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-auth-token": "o76dWE0IoKKjnwtCd7WOor9f1fbRh-gSuvE2OKIE11A",
        "x-user-id": "TBJJ3rQJc5bQRDygB",
    }
    
    response = requests.get(url, params=params, headers=headers, cookies=None)

    return response

def fetch_directory(start_offset):
    print('Fetching', start_offset)
    result = send_directory_request(10, start_offset).json()['result']
    return result

def get_total():
    return send_directory_request(count=1).json()['total']

def update_rocket_db(num_threads=15):
    t = get_total()
    print(f'Fetching {t} users with {num_threads} threads')

    # Using ThreadPoolExecutor to run the fetch_directory function in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        offsets = range(0, t, 10)
        
        # Using map to apply the function to each offset in parallel
        results = list(executor.map(fetch_directory, offsets))

    # Combine the results from all threads into a single list
    r = [item for sublist in results for item in sublist]
    users = {}
    for c, i in enumerate(r):
        users[i['username']] = r.pop(c)
        if 'name' in users[i['username']] and users[i['username']]['name'] is None:
            users[i['username']].pop('name')
        users[i['username']].pop('username')

    with open('./data/rocket_users.json', 'w') as f:
        json.dump(users, f, indent=4)

    print('Saved to rocket_users.json with', len(r), 'users')

def get_name_by_username(user:str):
    with open('./data/rocket_users.json', 'r') as f:
        users = json.load(f)
    
    if user in users:
        if 'name' in users[user]:
            return users[user]['name']
        else:
            return None 

def get_user_by_name(name:str):
    with open('./data/rocket_users.json', 'r') as f:
        users = json.load(f)
    for user in users:
        if 'name' in users[user] and users[user]['name'].upper() == name.upper():
            return users[user]
    return None  

if __name__ == '__main__':
    update_rocket_db()