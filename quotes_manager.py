"""
Quotes manager for receiving, storing, and analyzing live forex quotes.

This module owns the quote state and Bellman-Ford graph used to detect
arbitrage opportunities. It returns structured events instead of printing so
CLI, API, and web layers can decide how to present changes.
"""
from datetime import datetime, timedelta
import math
import threading

import bellman_ford


DEFAULT_START_AMOUNT = 100
DEFAULT_START_CURRENCY = 'USD'
QUOTE_EXPIRY_SECONDS = 1.5


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

    @staticmethod
    def _event(event_type, **payload):
        event = {'type': event_type}
        event.update(payload)
        return event

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

        :return: list of structured quote_expired events
        """
        curr_time = datetime.utcnow()

        # expiry time of 1.5 seconds
        expiry_limit = curr_time - timedelta(seconds=QUOTE_EXPIRY_SECONDS)
        events = []

        with self.lock:
            # identify expired quotes by their key
            expiry_keys = [
                quote_key
                for quote_key, quote_info in self.latest_valid_quotes.items()
                if quote_info['time'] < expiry_limit
            ]

            # remove expired quotes from `latest_valid_quotes` and the Bellman-Ford graph
            for key in expiry_keys:
                quote_info = self.latest_valid_quotes[key]
                del self.latest_valid_quotes[key]
                currency1, currency2 = key.split('/')
                self.forexGraph.remove_edge(currency1, currency2)
                self.forexGraph.remove_edge(currency2, currency1)
                events.append(self._event(
                    'quote_expired',
                    cross=key,
                    currency1=currency1,
                    currency2=currency2,
                    price=quote_info['price'],
                    time=quote_info['time'],
                ))

        return events

    def process_quotes(self, quotes):
        """
        Processes incoming quotes, updates valid quotes and the graph, removes
        expired quotes, and checks for arbitrage opportunities.
        -- after each message update, will try to locate possible arbitrage --

        :param:
            quotes (list): List of quotes where each quote contains `cross`, `price`, and `time`
        :return: list of structured events describing quote and arbitrage changes
        """
        events = []

        for quote in quotes:
            currency_pair = quote['cross']
            currency1, currency2 = currency_pair.split('/')
            with self.lock:
                latest_quote = self.latest_valid_quotes.get(currency_pair)

                # if it's a new quote, or the timestamp is greater than what we have already seen
                # -- uses older non-stale quotes when appropriate --
                if latest_quote is None or quote['time'] > latest_quote['time']:
                    self.latest_valid_quotes[currency_pair] = {
                        'price': quote['price'],
                        'time': quote['time']
                    }
                    events.append(self._event(
                        'quote_updated',
                        cross=currency_pair,
                        currency1=currency1,
                        currency2=currency2,
                        price=quote['price'],
                        time=quote['time'],
                    ))

                self.update_graph(currency1, currency2, quote['price'])

                latest_quote = self.latest_valid_quotes[currency_pair]
                if quote['time'] < latest_quote['time']:
                    events.append(self._event(
                        'quote_ignored',
                        reason='out_of_order',
                        cross=currency_pair,
                        currency1=currency1,
                        currency2=currency2,
                        price=quote['price'],
                        time=quote['time'],
                        latest_time=latest_quote['time'],
                    ))

            # remove expired quotes
            events.extend(self.remove_expired_quotes())

            # start arbitrage detection on valid quotes, always starting with 'USD'
            with self.lock:
                _dist, prev, neg_edge = self.forexGraph.shortest_paths(
                    DEFAULT_START_CURRENCY)
                if neg_edge is not None:
                    events.append(self.construct_cycle(neg_edge, prev))
                    # only 1 loop needed, return after found
                    return events

        return events

    def construct_cycle(self, neg_edge, prev):
        """
        Constructs an arbitrage cycle based on negative edges and exchange rates.

        :param:
            neg_edge (tuple): Edge where negative cycle was detected.
            prev (dict): Previous node for each currency in the shortest path.
        :return: structured arbitrage_detected event
        """
        cycle = []
        curr = neg_edge[0]
        # trace from back to beginning and reverse for correct order
        while curr is not None:
            cycle.append(curr)
            curr = prev[curr]
        cycle.reverse()

        exchanges, end_amount = self.build_exchanges(cycle, DEFAULT_START_AMOUNT)

        return self._event(
            'arbitrage_detected',
            edge={'from': neg_edge[0], 'to': neg_edge[1]},
            cycle=cycle,
            closed_cycle=cycle + [cycle[0]] if cycle else [],
            exchanges=exchanges,
            start_currency=cycle[0] if cycle else DEFAULT_START_CURRENCY,
            start_amount=DEFAULT_START_AMOUNT,
            end_amount=end_amount,
            profit=end_amount - DEFAULT_START_AMOUNT,
            profit_percent=((end_amount / DEFAULT_START_AMOUNT) - 1) * 100,
        )

    def build_exchanges(self, cycle, start_amount):
        """
        Builds exchange steps for an arbitrage cycle.

        :param:
            cycle (list): List of currencies in the arbitrage cycle.
            start_amount (float): Starting amount for the first currency.
        :return: exchange step list and final amount
        """
        if not cycle:
            return [], start_amount

        exchanges = []
        curr_amount = start_amount

        for i in range(len(cycle) - 1):
            from_ = cycle[i]
            to_ = cycle[i + 1]
            curr_amount = self.add_exchange(exchanges, from_, to_, curr_amount)

        # complete the arbitrage loop by looping back to the first currency
        curr_amount = self.add_exchange(
            exchanges,
            cycle[len(cycle) - 1],
            cycle[0],
            curr_amount,
        )
        return exchanges, curr_amount

    def add_exchange(self, exchanges, from_, to_, amount):
        weight = self.forexGraph.edges[from_][to_]
        rate = math.exp(-weight)
        next_amount = amount * rate
        exchanges.append({
            'from': from_,
            'to': to_,
            'rate': rate,
            'amount_before': amount,
            'amount_after': next_amount,
        })
        return next_amount
