"""
lab3.py
Junwen Zheng
Version: Oct 30, 2024 -- added comments for submission

This file implements a UDP subscriber system for receiving, managing, and analyzing real-time
forex quotes, aiming to detect arbitrage opportunities between currency pairs.

Overview:
    - `QuotesManager` class: Manages incoming forex quotes, updates an internal currency graph,
      and detects arbitrage cycles using the Bellman-Ford algorithm.
    - `UDPSubscriber` class: Connects to a forex data provider via UDP, receives and decodes
      forex quotes, and feeds them into the `QuotesManager` for processing.
    - `main` function: Sets up the `QuotesManager` and `UDPSubscriber` instances, then runs
      the subscriber and monitors its status for clean shutdown when no messages are received.

"""
from datetime import datetime, timedelta
import bellman_ford
import fxp_bytes_subscriber
import socket
import threading
import math

class QuotesManager:
    """
    Manages real-time forex quotes, updates a graph for currency relationships,
    and detects arbitrage opportunities using Bellman-Ford.

    Attributes:
        latest_valid_quotes (dict): Stores the latest valid quotes with timestamps.
        lock (threading.Lock): Thread lock for accessing shared resources.
        forexGraph (BellmanFord): Graph object to manage currency pairs as edges.
    """
    def __init__(self):
        """
        Initializes QuotesManager with an empty quote dictionary, thread lock,
        and Bellman-Ford graph.

        :returns: an QuotesManager object
        """
        self.latest_valid_quotes = {}
        self.lock = threading.Lock()
        self.forexGraph = bellman_ford.BellmanFord()

    def update_graph(self, currency1, currency2, price):
        """
         Updates the graph with a new price for a currency pair, using provided Bellman-Ford method

        :param:
            currency1 (str): The "from" currency.
            currency2 (str): The "to" currency.
            price (float): The exchange rate from currency1 to currency2.
        """

        # calculate log exchange rate required by Bellman-Ford class, both ways
        weight_1_2 = -math.log(price)
        weight_2_1 = math.log(price)

        self.forexGraph.add_edge(currency1, currency2, weight_1_2)
        self.forexGraph.add_edge(currency2, currency1, weight_2_1)

    def remove_expired_quotes(self):
        """
        Removes expired quotes from `latest_valid_quotes` and updates the graph
        by removing edges for those quotes.
        """
        curr_time = datetime.utcnow()

        # expiry time of 1.5 seconds
        expiry_limit = curr_time - timedelta(seconds=1.5)

        expiry_keys = []

        # identity expired quotes by their key
        for quote_key, quote_info in self.latest_valid_quotes.items():
            if quote_info['time'] < expiry_limit:
                expiry_keys.append(quote_key)

        # removing expired quotes from `latest_valid_quotes` and the Bellman-Ford graph
        with self.lock:
            for key in expiry_keys:
                print(f"Removing expired quote for {key}")
                del self.latest_valid_quotes[key]
                currency1, currency2 = key.split('/')
                self.forexGraph.remove_edge(currency1, currency2)
                self.forexGraph.remove_edge(currency2, currency1)

    def process_quotes(self, quotes):
        """
        Processes incoming quotes, updates valid quotes and the graph, removes
        expired quotes, and checks for arbitrage opportunities.
        -- after each message update, will try to locate possible arbitrage --

        :param:
            quotes (list): List of quotes where each quote contains `cross`, `price`, and `time`
        """
        for quote in quotes:
            currency_pair = quote['cross']
            currency1, currency2 = currency_pair.split('/')
            with self.lock:
                # if it's a new quote, or the timestamp is greater than what we have already seen
                # -- uses older non-stale quotes when appropriate --
                if (currency_pair not in self.latest_valid_quotes
                ) or (quote['time'] > self.latest_valid_quotes[currency_pair]['time']):
                    # add quote to `latest_valid_quotes`
                    self.latest_valid_quotes[currency_pair] = {
                        'price': quote['price'],
                        'time': quote['time']
                    }
                    print(f"{quote['time']} {currency1} {currency2} {quote['price']}")
                self.update_graph(currency1, currency2, quote['price'])

                '''
                print out if ignored an out of order quote
                not necessary because the condition to add quotes into `latest_valid_quotes`
                already excluding out of order quotes
                '''
                if quote['time'] < self.latest_valid_quotes[currency_pair]['time']:
                    print("Ignoring out of order quote")

            # remove expired quotes
            self.remove_expired_quotes()

            # start arbitrage detection on valid quotes, always starting with 'USD'
            dist, prev, neg_edge = self.forexGraph.shortest_paths('USD')
            if neg_edge is not None:
                print(f"\nArbitrage detected: {neg_edge}, {prev}, {dist}")
                self.construct_cycle(neg_edge, prev)
                # only 1 loop needed, return after found
                return

    def construct_cycle(self, neg_edge, prev):
        """
        Constructs an arbitrage cycle based on negative edges and prints the cycle
        along with exchange rates.

        :param:
            neg_edge (tuple): Edge where negative cycle was detected.
            prev (dict): Previous node for each currency in the shortest path.
        """
        cycle = []
        curr = neg_edge[0]
        # trace from back to beginning and reverse for correct order
        while curr is not None:
            cycle.append(curr)
            curr = prev[curr]
        cycle.reverse()

        # also trace exchange rates for output later
        exchange_rates = []
        for i in range(len(cycle) - 1):
            from_ = cycle[i]
            to_ = cycle[i + 1]
            weight = self.forexGraph.edges[from_][to_]
            rate = math.exp(-weight)
            exchange_rates.append(rate)

        self.print_cycle(cycle, exchange_rates)

    def print_cycle(self, cycle, exchange_rates):
        """
        Prints the sequence of exchanges in the arbitrage cycle with respective
        exchange rates and currency values.

        :param:
            cycle (list): List of currencies in the arbitrage cycle.
            exchange_rates (list): List of exchange rates for each step in the cycle.
        """
        init = 100
        curr = init

        print(f"\tstart with {cycle[0]} {init}")

        for i in range(len(exchange_rates)):
            from_ = cycle[i]
            to_ = cycle[i + 1]
            rate = exchange_rates[i]
            curr *= rate
            print(f"\texchange {from_} for {to_} at {rate:.10f} --> {to_} {curr:.10f}")

        # complete the arbitrage loop by looping back to 'USD'
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
    """
    Subscribes to forex_provider for UDP quotes (marshaled), unmarshal the quotes,
    and feed the quotes to QuotesManager.

    Attributes:
        server_addr (tuple): Address of the quote server.
        listen_ip (str): Local IP address to listen for UDP messages.
        listen_port (int): Local port to listen for UDP messages.
        addr (tuple): Tuple combining listen_ip and listen_port.
        socket (socket): UDP socket for communication.
        running (bool): Status indicating if the listener is active.
        quotes_manager (QuotesManager): class instance for managing quotes.
    """

    def __init__(self, server_addr, listen_ip, listen_port, quotes_manager):
        """
        Initializes UDPSubscriber with server and local configuration.

        :param:
            server_addr (tuple): Server address tuple (IP, port).
            listen_ip (str): IP address for listening.
            listen_port (int): Port for listening.
            quotes_manager (QuotesManager): Instance to manage quotes.
        """
        self.server_addr = server_addr
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.addr = (self.listen_ip, self.listen_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.addr)
        self.running = False
        self.quotes_manager = quotes_manager

    def connect(self):
        """
        Sends a subscription request of listening address to the server
        """
        self.socket.sendto(fxp_bytes_subscriber.marshal_sub_request
                           (self.listen_ip, self.listen_port), self.server_addr)

    def listen(self):
        """
        Listens for incoming UDP messages, processes quotes, and stops if no
        messages arrive within a timeout.
        """
        timeout = 5
        self.socket.settimeout(timeout)

        while self.running:
            try:
                incoming_bytes = self.socket.recv(4096)
                if incoming_bytes:
                    unprocessed_quotes = fxp_bytes_subscriber.unmarshal_quotes(
                        incoming_bytes)

                    # feed quotes to QuoteManager
                    self.quotes_manager.process_quotes(unprocessed_quotes)
                    # reset the timeout after receiving data
                    self.socket.settimeout(timeout)
            except socket.timeout:
                print(
                    f"No incoming messages for {timeout} seconds. Shutting down...")
                self.stop_running()
            except socket.error as e:
                print(f"Socket error: {e}")
                self.stop_running()
            except Exception as e:
                print(f"Error: {e}")
                self.stop_running()

    def start_listener_thread(self):
        """
        Starts the listener in a separate thread
        """
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















