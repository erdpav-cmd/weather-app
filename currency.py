#!/usr/bin/env python3
"""
Конвертер валют — средний уровень
Запуск: python currency.py
"""

import requests
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# ==================== КОНСТАНТЫ ====================
BASE_URL = "https://open.er-api.com/v6/latest/{base_code}"
CACHE_FILE = "currency_rate.json"
CACHE_TTL_HOURS = 24

# ==================== API CLIENT ====================
def get_currency_rate(base_code: str) -> Optional[Dict]:
    """Делает GET-запрос к API и возвращает данные о курсах валют."""
    url = BASE_URL.format(base_code=base_code.upper())
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Ошибка HTTP {response.status_code}: {response.reason}")
            return None
        
        data = response.json()
        
        if data.get("result") != "success":
            print(f"❌ API ошибка: {data.get('error-type', 'unknown')}")
            return None
            
        return data
        
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка сети: проверьте подключение к интернету")
        return None
    except requests.exceptions.Timeout:
        print("❌ Таймаут: сервер не ответил вовремя")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка запроса: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return None


def get_rates(data: Dict) -> Dict:
    """Получает курсы из ответа API (поддерживает оба формата ключей)."""
    if "rates" in data:
        return data["rates"]
    elif "conversion_rates" in data:
        return data["conversion_rates"]
    return {}


def get_supported_currencies(data: Dict) -> List[str]:
    """Возвращает список доступных кодов валют из ответа API."""
    rates = get_rates(data)
    return list(rates.keys())


def convert_amount(data: Dict, from_currency: str, to_currency: str, amount: float) -> Optional[float]:
    """Конвертирует сумму из одной валюты в другую."""
    rates = get_rates(data)
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    
    if from_currency not in rates:
        print(f"❌ Валюта '{from_currency}' не найдена в доступных курсах")
        return None
    if to_currency not in rates:
        print(f"❌ Валюта '{to_currency}' не найдена в доступных курсах")
        return None
    
    base_code = data.get("base_code", "").upper()
    
    if from_currency == base_code:
        result = amount * rates[to_currency]
    elif to_currency == base_code:
        result = amount / rates[from_currency]
    else:
        result = amount * (rates[to_currency] / rates[from_currency])
    
    return round(result, 4)

# ==================== STORAGE ====================
def save_to_file(data: Dict, path: str = CACHE_FILE) -> bool:
    """Сохраняет данные в JSON-файл с форматированием."""
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        return True
    except IOError as e:
        print(f"❌ Ошибка записи в файл: {e}")
        return False


def read_from_file(path: str = CACHE_FILE) -> Optional[Dict]:
    """Читает данные из JSON-файла."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (IOError, json.JSONDecodeError) as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return None


def is_cache_valid(path: str = CACHE_FILE) -> bool:
    """Проверяет, актуален ли кэш (моложе 24 часов)."""
    if not os.path.exists(path):
        return False
    try:
        mtime = os.path.getmtime(path)
        file_time = datetime.fromtimestamp(mtime)
        return datetime.now() - file_time < timedelta(hours=CACHE_TTL_HOURS)
    except OSError:
        return False


def get_fresh_or_cached_data(base_code: str) -> Optional[Dict]:
    """Возвращает данные: из кэша если актуален, иначе — свежий запрос к API."""
    if is_cache_valid(CACHE_FILE):
        cached = read_from_file(CACHE_FILE)
        if cached and cached.get("base_code", "").upper() == base_code.upper():
            print("✅ Используем кэшированные данные")
            return cached
    
    print("🔄 Запрашиваем актуальные данные...")
    data = get_currency_rate(base_code)
    
    if data:
        save_to_file(data)
        print(f"💾 Данные сохранены в {CACHE_FILE}")
    
    return data

# ==================== CLI INTERFACE ====================
def display_rates(data: Dict, target_currencies: Optional[List[str]] = None):
    """Выводит курсы валют в удобном формате."""
    base = data.get("base_code", "UNKNOWN")
    rates = get_rates(data)  # ИСПРАВЛЕНО: используем get_rates()
    
    print(f"\n📊 Курсы валют от {data.get('time_last_update_utc', 'N/A')}")
    print(f"🔹 Базовая валюта: {base}\n")
    
    currencies_to_show = target_currencies if target_currencies else ["RUB", "EUR", "GBP"]
    
    for code in currencies_to_show:
        if code in rates:
            print(f"  {base} → {code}: {rates[code]:.4f}")
        else:
            print(f"  {base} → {code}: ❌ нет данных")


def run_converter():
    """Основной интерактивный цикл программы."""
    print("🌍 Конвертер валют — средний уровень")
    print("Введите 'exit' или 'quit' в любой момент для выхода.\n")
    
    while True:
        base = input("🔹 Базовая валюта (например, USD): ").strip().upper()
        
        if base.lower() in ("exit", "quit", "выход"):
            print("👋 До свидания!")
            break
        if not base or len(base) != 3:
            print("⚠️  Введите корректный 3-буквенный код валюты (например, USD)\n")
            continue
        
        data = get_fresh_or_cached_data(base)
        if not data:
            print("⚠️  Не удалось получить данные. Попробуйте позже.\n")
            continue
        
        valid_currencies = get_supported_currencies(data)
        
        print("\n📋 Доступные действия:")
        print("  1 — Показать курсы для RUB, EUR, GBP")
        print("  2 — Конвертировать сумму")
        print("  3 — Показать все доступные валюты")
        print("  0 — Выход")
        
        choice = input("\nВаш выбор: ").strip()
        
        if choice == "1":
            display_rates(data, ["RUB", "EUR", "GBP"])
            
        elif choice == "2":
            from_curr = input("  Из валюты: ").strip().upper()
            if from_curr not in valid_currencies:
                print(f"❌ '{from_curr}' — недопустимый код валюты")
                continue
                
            to_curr = input("  В валюту: ").strip().upper()
            if to_curr not in valid_currencies:
                print(f"❌ '{to_curr}' — недопустимый код валюты")
                continue
                
            try:
                amount = float(input("  Сумма: ").strip())
                if amount < 0:
                    raise ValueError
            except ValueError:
                print("❌ Введите корректное неотрицательное число")
                continue
                
            result = convert_amount(data, from_curr, to_curr, amount)
            if result is not None:
                print(f"\n✅ {amount:,.2f} {from_curr} = {result:,.4f} {to_curr}")
                
        elif choice == "3":
            print(f"\n📦 Доступно валют: {len(valid_currencies)}")
            sorted_currencies = sorted(valid_currencies)
            for i in range(0, len(sorted_currencies), 20):
                print("  " + ", ".join(sorted_currencies[i:i+20]))
                
        elif choice in ("0", "exit", "quit", "выход"):
            print("👋 До свидания!")
            break
        else:
            print("⚠️  Неверный выбор, попробуйте снова")
        
        print("\n" + "-" * 60 + "\n")


# ==================== ЗАПУСК ПРОГРАММЫ ====================
if __name__ == "__main__":
    print("🚀 Конвертер валют запущен!")
    print("-" * 50)
    run_converter()