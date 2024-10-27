import bellman_ford
import fxp_bytes_subscriber
import socket
import threading

REQUEST_ADDRESS = ('localhost', 10101)

class CurrencyNode:
    def __init__(self, ISO_code, exchange_rate):
        self.ISO_code = ISO_code
        self.exchange_rate = exchange_rate


class UDPSubscriber:
    def __init__(self, server_addr, listen_ip, listen_port):
        self.server_addr = server_addr
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.addr = (self.listen_ip, self.listen_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.addr)
        self.running = False
        self.valid_quotes = {}

    def connect(self):
        self.socket.sendto(fxp_bytes_subscriber.marshal_sub_request
                           (self.listen_ip, self.listen_port), self.server_addr)

    def listen(self):
        while self.running:
            incoming_bytes = self.socket.recv(4096)
            unprocessed_quotes = fxp_bytes_subscriber.unmarshal_quotes(incoming_bytes)
            self.process_quotes(unprocessed_quotes)

    def process_quotes(self, quotes):
        for quote in quotes:
            currency_pair = quote['cross']
            if currency_pair not in self.valid_quotes:
                self.valid_quotes[currency_pair] = {
                    'price': quote['price'],
                    'time': quote['time']
                }
                print(f"New quote detected, adding:{currency_pair}: {self.valid_quotes[currency_pair]}")

            if quote['time'] > self.valid_quotes[currency_pair]['time']:
                self.valid_quotes[currency_pair] = {
                    'price': quote['price'],
                    'time': quote['time']
                }
                print(f"Existing quote detected, replacing with new quote:{currency_pair}: {self.valid_quotes[currency_pair]}")

            ## no need for out-of-order detection since new quotes are only added if it has bigger timestamp
            # if (currency_pair in self.valid_quotes) and (
            #         quote['time'] < self.valid_quotes[currency_pair]['time']):
            #     # Detected an out-of-order quote, ignore it
            #     print(
            #         f"****Detected out-of-order quote for {currency_pair} with timestamp {quote['time']}")
            #     continue


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











