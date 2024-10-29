from datetime import datetime, timedelta
import bellman_ford
import fxp_bytes_subscriber
import socket
import threading
import math

REQUEST_ADDRESS = ('localhost', 10101)

class QuotesManager:
    def __init__(self):
        self.latest_valid_quotes = {}
        self.lock = threading.Lock()
        self.forexGraph = bellman_ford.BellmanFord()

    def update_graph(self, currency1, currency2, price):
        weight_1_2 = -math.log(price)
        weight_2_1 = math.log(price)

        self.forexGraph.add_edge(currency1, currency2, weight_1_2)
        self.forexGraph.add_edge(currency2, currency1, weight_2_1)

    def remove_expired_quotes(self):
        curr_time = datetime.utcnow()
        # todo: fix expiry time limit
        expiry_limit = curr_time - timedelta(seconds=3)

        expiry_keys = []

        for quote_key, quote_info in self.latest_valid_quotes.items():
            if quote_info['time'] < expiry_limit:
                expiry_keys.append(quote_key)
        with self.lock:
            for key in expiry_keys:
                print(f"Removing expired quote for {key}")
                del self.latest_valid_quotes[key]
                currency1, currency2 = key.split('/')
                self.forexGraph.remove_edge(currency1, currency2)
                self.forexGraph.remove_edge(currency2, currency1)

    def process_quotes(self, quotes):
        for quote in quotes:
            currency_pair = quote['cross']
            currency1, currency2 = currency_pair.split('/')
            with self.lock:
                if (currency_pair not in self.latest_valid_quotes
                ) or (quote['time'] > self.latest_valid_quotes[currency_pair]['time']):
                    self.latest_valid_quotes[currency_pair] = {
                        'price': quote['price'],
                        'time': quote['time']
                    }
                    print(f"{quote['time']} {currency1} {currency2} {quote['price']:.2f}")
                self.update_graph(currency1, currency2, quote['price'])

            self.remove_expired_quotes()

            dist, prev, neg_edge = self.forexGraph.shortest_paths('USD')
            if neg_edge is not None:
                print(f"Arbitrage detected: {neg_edge}, {prev}, {dist}")
                self.construct_cycle(neg_edge, prev)
                return

    def construct_cycle(self, neg_edge, prev):
        cycle = []
        curr = neg_edge[0]
        while curr is not None:
            cycle.append(curr)
            curr = prev[curr]

        cycle.reverse()

        exchange_rates = []
        for i in range(len(cycle) - 1):
            from_ = cycle[i]
            to_ = cycle[i + 1]
            weight = self.forexGraph.edges[from_][to_]
            rate = math.exp(-weight)
            exchange_rates.append(rate)

        self.print_cycle(cycle, exchange_rates)

    def print_cycle(self, cycle, exchange_rates):
        init = 100
        curr = init

        print(f"\tstart with {cycle[0]} {init}")

        for i in range(len(exchange_rates)):
            from_ = cycle[i]
            to_ = cycle[i + 1]
            rate = exchange_rates[i]
            curr *= rate
            print(f"\texchange {from_} for {to_} at {rate:.10f} --> {to_} {curr:.10f}")

        self.end_with(cycle, curr)

    def end_with(self, cycle, curr):
        from_ = cycle[len(cycle) - 1]
        to_ = cycle[0]
        weight = self.forexGraph.edges[from_][to_]
        rate = math.exp(-weight)
        final = curr * rate
        print(f"\texchange {from_} for {to_} at {rate:.10f} --> {to_} {final:.10f}")
        print(f"\tend with {cycle[0]} {final:.10f}\n")


class UDPSubscriber:
    def __init__(self, server_addr, listen_ip, listen_port, quotes_manager):
        self.server_addr = server_addr
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.addr = (self.listen_ip, self.listen_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.addr)
        self.running = False
        self.quotes_manager = quotes_manager

    def connect(self):
        self.socket.sendto(fxp_bytes_subscriber.marshal_sub_request
                           (self.listen_ip, self.listen_port), self.server_addr)

    # def listen(self):
    #     while self.running:
    #         incoming_bytes = self.socket.recv(4096)
    #         unprocessed_quotes = fxp_bytes_subscriber.unmarshal_quotes(incoming_bytes)
    #         self.quotes_manager.process_quotes(unprocessed_quotes)

    def listen(self):
        while self.running:
            try:
                incoming_bytes = self.socket.recv(4096)
                if incoming_bytes:
                    unprocessed_quotes = fxp_bytes_subscriber.unmarshal_quotes(
                        incoming_bytes)
                    self.quotes_manager.process_quotes(unprocessed_quotes)
            except socket.error as e:
                print(f"Socket error: {e}")
                self.stop_running()
            except Exception as e:
                print(f"Error: {e}")
                self.stop_running()

    def start_listener_thread(self):
        listener_thread = threading.Thread(target=self.listen)
        listener_thread.daemon = True
        listener_thread.start()

    def run(self):
        self.running = True
        self.connect()
        self.start_listener_thread()

    def stop_running(self):
        self.running = False
        self.socket.close()
        print("Subscriber stopped. Socket closed.")


if __name__ == '__main__':
    quotes_manager = QuotesManager()
    sub = UDPSubscriber(REQUEST_ADDRESS, '127.0.0.1', 50000, quotes_manager)
    sub.run()
    while True:
        pass














