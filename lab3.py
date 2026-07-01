"""
lab3.py
Junwen Zheng
Version: Oct 30, 2024 -- added comments for submission

This file orchestrates a UDP subscriber system for receiving, managing, and
analyzing real-time forex quotes, aiming to detect arbitrage opportunities
between currency pairs.

Overview:
    - `main` function: Sets up the `QuotesManager` and `UDPSubscriber`
      instances, then runs the subscriber and monitors its status for clean
      shutdown when no messages are received.
"""
import threading

from quotes_manager import QuotesManager
from udp_subscriber import UDPSubscriber


def main():
    server_ip = input("Enter server IP (for localhost enter 127.0.0.1): ")
    server_port = int(input("Enter server port: "))
    listen_ip = input("Enter listen IP (for localhost enter 127.0.0.1): ")
    listen_port = int(input("Enter listen port: "))
    server_addr = (server_ip, server_port)

    quotes_manager = QuotesManager()

    subscriber = UDPSubscriber(server_addr, listen_ip, listen_port, quotes_manager)

    # hard coded main for testing purposes
    # REQUEST_ADDRESS = ('localhost', 10101)
    # subscriber = UDPSubscriber(REQUEST_ADDRESS, '127.0.0.1', 50505, quotes_manager)

    subscriber.run()

    try:
        while subscriber.running:
            threading.Event().wait(0.1)
    except KeyboardInterrupt:
        print("Interrupted manually")
    finally:
        exit(0)


if __name__ == '__main__':
    main()
