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


def format_event(event):
    event_type = event.get('type')

    if event_type == 'quote_updated':
        return (
            f"{event['time']} {event['currency1']} "
            f"{event['currency2']} {event['price']}"
        )

    if event_type == 'quote_expired':
        return f"Removing expired quote for {event['cross']}"

    if event_type == 'quote_ignored':
        if event.get('reason') == 'out_of_order':
            return "Ignoring out of order quote"
        return f"Ignoring quote for {event['cross']}"

    if event_type == 'arbitrage_detected':
        return format_arbitrage_event(event)

    if event_type == 'subscriber_error':
        return event['message']

    if event_type == 'subscriber_stopped':
        lines = []
        if event.get('message'):
            lines.append(event['message'])
        lines.append("Subscriber stopped. Socket closed.")
        return "\n".join(lines)

    return None


def format_arbitrage_event(event):
    edge = event['edge']
    lines = [
        f"Arbitrage detected involving edges: ({edge['from']!r}, {edge['to']!r})",
        f"\tstart with {event['start_currency']} {event['start_amount']}",
    ]

    for exchange in event['exchanges']:
        lines.append(
            f"\texchange {exchange['from']} for {exchange['to']} "
            f"at {exchange['rate']:.10f} --> "
            f"{exchange['to']} {exchange['amount_after']:.10f}"
        )

    lines.append(f"\tend with {event['start_currency']} {event['end_amount']:.10f}\n")
    return "\n".join(lines)


def print_event(event):
    message = format_event(event)
    if message:
        print(message)


def main():
    server_ip = input("Enter server IP (for localhost enter 127.0.0.1): ")
    server_port = int(input("Enter server port: "))
    listen_ip = input("Enter listen IP (for localhost enter 127.0.0.1): ")
    listen_port = int(input("Enter listen port: "))
    server_addr = (server_ip, server_port)

    quotes_manager = QuotesManager()

    subscriber = UDPSubscriber(
        server_addr,
        listen_ip,
        listen_port,
        quotes_manager,
        event_handler=print_event,
    )

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
