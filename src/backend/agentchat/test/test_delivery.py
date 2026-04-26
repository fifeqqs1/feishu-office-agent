import os
import json
import ssl
import urllib.parse
import urllib.request
from datetime import datetime

import pytz

DELIVERY_HOST = 'https://qyexpress.market.alicloudapi.com/composite/queryexpress'

DELIVERY_KEY = os.getenv("DELIVERY_API_KEY", "")

DELIVERY_PROMPT = """
您的{}单号为{}的信息如下:
{}
"""

def delivery_action(number: str):
    query = f'number={number}&mobile=mobile&type=type'

    url = DELIVERY_HOST + '?' + query
    headers = {
        'Authorization': 'APPCODE ' + DELIVERY_KEY
    }

    request = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(request, context=ctx) as response:
        content = response.read().decode('utf-8')
        content = json.loads(content)
        company = content['data'].get('typename')
        result = []
        for data in content['data']['list']:
            result.append(f"时间为{data.get('time')}, 快递信息是: {data.get('status')}")
        result.reverse()
        final_result = DELIVERY_PROMPT.format(company, number, result)

        return final_result

if __name__ == "__main__":
    if DELIVERY_KEY:
        print(delivery_action("YOUR_TRACKING_NUMBER"))
    else:
        print("Set DELIVERY_API_KEY to run this manual test.")

    print(datetime.now(pytz.timezone('Asia/Shanghai')))
