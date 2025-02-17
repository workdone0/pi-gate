from multiprocessing import Process
from dns_server import start_dns_server
from dashboard import start_dashboard
from database import init_db

if __name__ == "__main__":
    init_db()  # Initialize database

    dns_process = Process(target=start_dns_server)
    dash_process = Process(target=start_dashboard)

    dns_process.start()
    dash_process.start()

    dns_process.join()
    dash_process.join()
