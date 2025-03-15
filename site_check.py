import requests
import time
import sqlite3
import pandas as pd
import threading
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def create_db():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization TEXT,
            timestamp TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_event(organization, status):
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs (organization, timestamp, status) VALUES (?, ?, ?)",
                   (organization, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status))
    conn.commit()
    conn.close()


def check_sites(sites):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    last_status = {site: None for site in sites}
    check_interval = 1

    while True:
        for site in sites:
            try:
                response = requests.get(site, headers=headers, timeout=check_interval, verify=False)
                if response.status_code == 200:
                    if last_status[site] != "Доступен":
                        log_event(site, "Доступен")
                    last_status[site] = "Доступен"
                else:
                    if last_status[site] != "Недоступен":
                        log_event(site, "Недоступен")
                    last_status[site] = "Недоступен"
            except requests.RequestException:
                if last_status[site] != "Ошибка":
                    log_event(site, "Ошибка")
                last_status[site] = "Ошибка"

        time.sleep(check_interval)


def generate_report(date=None):
    conn = sqlite3.connect("monitoring.db")
    df = pd.read_sql("SELECT * FROM logs", conn)
    conn.close()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    df = df[df["timestamp"].dt.strftime("%Y-%m-%d") == date].sort_values("timestamp")

    if df.empty:
        print(f"Нет данных за {date}")
        return

    report = []
    total_time = 86400

    for site in df["organization"].unique():
        site_data = df[df["organization"] == site]
        downtime = 0
        last_down_time = None

        for _, row in site_data.iterrows():
            if row["status"] == "Недоступен":
                if last_down_time is None:
                    last_down_time = row["timestamp"]
            else:
                if last_down_time is not None:
                    downtime += (row["timestamp"] - last_down_time).total_seconds()
                    last_down_time = None

        if last_down_time is not None:
            downtime += (datetime.strptime(date, "%Y-%m-%d").replace(hour=23, minute=59, second=59) - last_down_time).total_seconds()

        uptime = total_time - downtime
        uptime_percent = round((uptime / total_time) * 100, 2)
        report.append([site, f"{uptime_percent}%", f"{int(downtime)} секунд"])

    report_df = pd.DataFrame(report, columns=["Наименование организации", "Uptime (%)", "Общее время недоступности (сек.)"])
    report_filename = f"report_{date}.csv"
    report_df.to_csv(report_filename, index=False, mode='w')
    print(f"Отчёт за {date} сохранён в {report_filename}")



def user_input_listener():
    while True:
        command = input("Введите команду (report [YYYY-MM-DD] - запрос отчёта, exit - завершить выполнение программы): ").strip().lower()
        if command.startswith("report"):
            parts = command.split()
            date = parts[1] if len(parts) > 1 else None
            print(f"Генерация отчета за {date or 'сегодня'}...")
            generate_report(date)
        elif command == "exit":
            print("Завершение работы программы...")
            break



def main():
    create_db()
    sites = [
        "https://www.google.com/",
        "https://www.alfa-bank.ru/",
        "https://www.rgs.ru/",
        "https://finuslugi.ru/",
        "https://www.alfastrah.ru/"
    ]

    monitoring_thread = threading.Thread(target=check_sites, args=(sites,))
    user_thread = threading.Thread(target=user_input_listener)

    monitoring_thread.daemon = True
    monitoring_thread.start()

    user_input_listener()


if __name__ == "__main__":
    main()
