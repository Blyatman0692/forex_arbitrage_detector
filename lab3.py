from datetime import datetime, timedelta


import bellman_ford
import fxp_bytes_subscriber
import socket
import threading

REQUEST_ADDRESS = ('localhost', 10101)

class QuotesManager:
    def __init__(self):
        self.latest_valid_quotes = {}

    def process_quotes(self, quotes):
        for quote in quotes:
            currency_pair = quote['cross']
            if currency_pair not in self.latest_valid_quotes:
                self.latest_valid_quotes[currency_pair] = {
                    'price': quote['price'],
                    'time': quote['time']
                }
                print(
                    f"New quote detected, adding:{currency_pair}: "
                    f"{self.latest_valid_quotes[currency_pair]}")

            if quote['time'] > self.latest_valid_quotes[currency_pair]['time']:
                self.latest_valid_quotes[currency_pair] = {
                    'price': quote['price'],
                    'time': quote['time']
                }
                print(
                    f"Existing quote detected, replacing with new quote:{currency_pair}: "
                    f"{self.latest_valid_quotes[currency_pair]}")

        self.remove_expired_quotes()

    def remove_expired_quotes(self):
        curr_time = datetime.utcnow()
        # todo: fix expiry time limit
        expiry_limit = curr_time - timedelta(seconds=3)

        expiry_keys = []

        for quote_key, quote_info in self.latest_valid_quotes.items():
            if quote_info['time'] < expiry_limit:
                expiry_keys.append(quote_key)

        for key in expiry_keys:
            print(f"Removing expired quote for {key}")
            del self.latest_valid_quotes[key]

    def get_valid_quotes(self):
        return self.latest_valid_quotes

class UDPSubscriber:
    def __init__(self, server_addr, listen_ip, listen_port):
        self.server_addr = server_addr
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.addr = (self.listen_ip, self.listen_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.addr)
        self.running = False
        self.quotes_manager = QuotesManager()

    def connect(self):
        self.socket.sendto(fxp_bytes_subscriber.marshal_sub_request
                           (self.listen_ip, self.listen_port), self.server_addr)

    def listen(self):
        while self.running:
            incoming_bytes = self.socket.recv(4096)
            unprocessed_quotes = fxp_bytes_subscriber.unmarshal_quotes(incoming_bytes)
            self.quotes_manager.process_quotes(unprocessed_quotes)

    def start_listener_thread(self):
        listener_thread = threading.Thread(target=self.listen())
        listener_thread.daemon = True
        listener_thread.start()

    def run(self):
        self.running = True
        self.connect()
        self.start_listener_thread()


if __name__ == '__main__':
    sub = UDPSubscriber(REQUEST_ADDRESS, '127.0.0.1', 50000)
    sub.run()











