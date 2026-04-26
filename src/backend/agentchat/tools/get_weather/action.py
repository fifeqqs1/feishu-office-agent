import requests
from loguru import logger
from langchain.tools import tool

from agentchat.settings import app_settings
from agentchat.prompts.tool import WEATHER_PROMPT, MESSAGE_PROMPT


@tool(parse_docstring=True)
def get_weather(city: str):
    """
    查询用户提供城市的天气情况。

    Args:
        city (str): 用户提供的城市名称。

    Returns:
        str: 城市的天气信息。
    """
    return _get_weather(city)

def _get_weather(location: str):
    """帮助用户想要查询的天气"""
    params = {
        'key': app_settings.tools.weather.get('api_key'),
        'city': location,
        'extensions': 'all'
    }

    try:
        res = requests.get(url=app_settings.tools.weather.get('endpoint'), params=params, timeout=5)  # 预报天气
        result = res.json()
        if res.status_code != 200:
            return f"天气服务暂时不可用（HTTP {res.status_code}），请稍后再试。"

        if result.get("status") != "1":
            info = result.get("info") or "未知错误"
            if info == "INVALID_USER_KEY":
                return "天气服务当前不可用：天气 API Key 无效，请联系管理员检查配置。"
            return f"天气服务当前不可用：{info}"

        forecasts = result.get('forecasts') or []
        if not forecasts:
            return f"未查询到“{location}”的天气信息，请确认城市名称后再试。"

        city = forecasts[0].get("city")  # 获取城市
        message_result = []
        data = forecasts[0].get("casts") or []
        if not data:
            return f"未查询到“{location}”的天气预报数据，请稍后再试。"

        for item in data:
            date = item.get('date')  # 获取日期
            day_temp = item.get('daytemp')  # 白天温度
            night_temp = item.get('nighttemp')  # 晚上温度
            day_weather = item.get('dayweather')  # 白天天气现象
            night_weather = item.get('nightweather')  # 晚上天气现象
            weather_message = MESSAGE_PROMPT.format(date, day_temp, night_temp, day_weather, night_weather)

            message_result.append(weather_message)

        final_result = WEATHER_PROMPT.format(city, message_result[0], message_result[1:])
        return final_result
    except Exception as err:
        logger.error(f'Call Weather Tool Err: {err}')
        return str(err)

