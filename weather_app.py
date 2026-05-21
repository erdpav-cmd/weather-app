import requests
from dotenv import load_dotenv
import os
import json
from datetime import datetime, timedelta
import time

# Загрузка переменных окружения
load_dotenv()
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("Ошибка: API_KEY не найден в .env файле")
    exit(1)

CACHE_FILE = "weather_cache.json"


def save_to_cache(data: dict, city: str = None, lat: float = None, lon: float = None):
    """Сохраняет данные в кэш с метаданными"""
    cache_data = {
        "weather": data,
        "city": city,
        "lat": lat,
        "lon": lon,
        "fetched_at": datetime.now().isoformat()
    }
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Предупреждение: не удалось сохранить кэш: {e}")


def load_from_cache() -> dict | None:
    """Загружает данные из кэша, если файл существует"""
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Предупреждение: не удалось загрузить кэш: {e}")
        return None


def is_cache_valid(cache_data: dict, max_age_hours: int = 3) -> bool:
    """Проверяет, действителен ли кэш (не старше max_age_hours часов)"""
    if not cache_data:
        return False
    
    try:
        fetched_at = datetime.fromisoformat(cache_data["fetched_at"])
        age = datetime.now() - fetched_at
        return age < timedelta(hours=max_age_hours)
    except (KeyError, ValueError):
        return False


def make_request_with_retry(url: str, max_retries: int = 3) -> requests.Response | None:
    """Делает GET-запрос с повторами при ошибках 429 и сетевых проблемах"""
    retries = 0
    while retries <= max_retries:
        try:
            response = requests.get(url, timeout=10)
            
            # Если успех — возвращаем ответ
            if response.status_code == 200:
                return response
            
            # Если 429 (Too Many Requests) — делаем retry с экспоненциальной паузой
            if response.status_code == 429 and retries < max_retries:
                wait_time = 2 ** retries  # 1s, 2s, 4s
                print(f"Превышен лимит запросов. Повтор через {wait_time}с...")
                time.sleep(wait_time)
                retries += 1
                continue
            
            # Другие ошибки — не повторяем
            return response
            
        except requests.exceptions.RequestException as e:
            if retries < max_retries:
                wait_time = 2 ** retries
                print(f"Сетевая ошибка: {e}. Повтор через {wait_time}с...")
                time.sleep(wait_time)
                retries += 1
            else:
                print(f"Сетевая ошибка после {max_retries} попыток: {e}")
                return None
    
    return None


def get_coordinates(city: str) -> tuple[float, float] | None:
    """
    Получает координаты города через OpenWeather Geocoding API
    """
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&lang=ru&appid={API_KEY}"
    
    response = make_request_with_retry(url)
    
    if response is None:
        print("Ошибка: не удалось подключиться к серверу геокодинга")
        return None
    
    if response.status_code != 200:
        if response.status_code == 401:
            print("Ошибка: невалидный API ключ")
        else:
            print(f"Ошибка геокодинга: статус {response.status_code}")
        return None
    
    try:
        data = response.json()
        if not data:
            print(f"Город '{city}' не найден")
            return None
        
        lat = data[0].get('lat')
        lon = data[0].get('lon')
        
        if lat is None or lon is None:
            print(f"Не удалось получить координаты для города '{city}'")
            return None
        
        return float(lat), float(lon)
    
    except json.JSONDecodeError:
        print("Ошибка: некорректный ответ от сервера геокодинга")
        return None


def get_weather_by_coordinates(latitude: float, longitude: float) -> dict | None:
    """
    Получает погоду по координатам через OpenWeather Current Weather API
    """
    url = (f"https://api.openweathermap.org/data/2.5/weather?"
           f"lat={latitude}&lon={longitude}&appid={API_KEY}&units=metric&lang=ru")
    
    response = make_request_with_retry(url)
    
    if response is None:
        print("Ошибка: не удалось подключиться к серверу погоды")
        return None
    
    if response.status_code != 200:
        if response.status_code == 401:
            print("Ошибка: невалидный API ключ")
        elif response.status_code == 404:
            print("Ошибка: местоположение не найдено")
        else:
            print(f"Ошибка получения погоды: статус {response.status_code}")
        return None
    
    try:
        return response.json()
    except json.JSONDecodeError:
        print("Ошибка: некорректный ответ от сервера погоды")
        return None


def get_weather_by_city(city: str) -> dict | None:
    """Получает погоду по названию города"""
    coords = get_coordinates(city)
    if not coords:
        return None
    
    lat, lon = coords
    weather = get_weather_by_coordinates(lat, lon)
    
    if weather:
        save_to_cache(weather, city=city, lat=lat, lon=lon)
    
    return weather


def print_weather(weather: dict, city_name: str = None):
    """Выводит информацию о погоде в красивом формате"""
    if not weather:
        return
    
    city = weather.get('name', city_name or 'Неизвестный город')
    temp = weather.get('main', {}).get('temp')
    description = weather.get('weather', [{}])[0].get('description', 'нет данных')
    
    if temp is not None:
        print(f"\nПогода в {city}: {temp}°C, {description}\n")
    else:
        print("Не удалось получить информацию о температуре")


def menu_mode():
    """Режим с меню выбора (1 - по городу, 2 - по координатам, 0 - выход)"""
    while True:
        print("\n=== Меню ===")
        print("1 - Получить погоду по городу")
        print("2 - Получить погоду по координатам")
        print("0 - Выход")
        
        choice = input("\nВыберите режим: ").strip()
        
        if choice == '0':
            print("До свидания!")
            break
        
        elif choice == '1':
            city = input("Введите название города: ").strip()
            if not city:
                print("Город не может быть пустым")
                continue
            
            weather = get_weather_by_city(city)
            
            if weather:
                print_weather(weather, city)
            else:
                # Предлагаем данные из кэша
                cache_data = load_from_cache()
                if is_cache_valid(cache_data):
                    use_cache = input("Не удалось получить свежие данные. Использовать кэш? (y/n): ").strip().lower()
                    if use_cache == 'y' and cache_data:
                        print_weather(cache_data['weather'], cache_data.get('city'))
        
        elif choice == '2':
            try:
                lat = float(input("Введите широту: ").strip())
                lon = float(input("Введите долготу: ").strip())
            except ValueError:
                print("Некорректные координаты")
                continue
            
            weather = get_weather_by_coordinates(lat, lon)
            
            if weather:
                print_weather(weather)
                save_to_cache(weather, lat=lat, lon=lon)
            else:
                # Предлагаем данные из кэша
                cache_data = load_from_cache()
                if is_cache_valid(cache_data):
                    use_cache = input("Не удалось получить свежие данные. Использовать кэш? (y/n): ").strip().lower()
                    if use_cache == 'y' and cache_data:
                        print_weather(cache_data['weather'], cache_data.get('city'))
        
        else:
            print("Неверный выбор. Попробуйте снова.")


def simple_mode():
    """Простой режим: только запрос города"""
    city = input("Введите название города: ").strip()
    if not city:
        print("Город не может быть пустым")
        return
    
    weather = get_weather_by_city(city)
    
    if weather:
        print_weather(weather, city)
    else:
        # Предлагаем данные из кэша
        cache_data = load_from_cache()
        if is_cache_valid(cache_data):
            use_cache = input("Не удалось получить свежие данные. Использовать кэш? (y/n): ").strip().lower()
            if use_cache == 'y' and cache_data:
                print_weather(cache_data['weather'], cache_data.get('city'))


if __name__ == "__main__":
    print("=== Приложение погоды ===")
    print("Выберите режим работы:")
    print("1 - Простой режим (только город)")
    print("2 - Расширенный режим (меню)")
    
    mode = input("\nВаш выбор: ").strip()
    
    if mode == '2':
        menu_mode()
    else:
        simple_mode()