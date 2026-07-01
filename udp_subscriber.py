"""
UDP subscriber for the Forex Provider quote feed.

This module handles socket subscription, message receiving, and quote
unmarshalling before handing decoded quotes to a QuotesManager. It can forward
structured events to an optional event handler.
"""
import socket
import threading

import fxp_bytes_subscriber


class UDPSubscriber:
    """
    Subscribes to forex_provider for UDP quotes (marshaled), unmarshal the quotes,
    and feed the quotes to QuotesManager.

    Attributes:
        server_addr (tuple): Address of the quote server.
        listen_ip (str): Local IP address to listen for UDP messages.
        listen_port (int): Port to listen on.
        addr (tuple): Tuple combining listen_ip and listen_port.
        socket (socket): UDP socket for communication.
        running (bool): Status indicating if the listener is active.
        quotes_manager (QuotesManager): class instance for managing quotes.
    """

    def __init__(
            self,
            server_addr,
            listen_ip,
            listen_port,
            quotes_manager,
            event_handler=None):
        """
        Initializes UDPSubscriber with server and local configuration.

        :param:
            server_addr (tuple): Server address tuple (IP, port).
            listen_ip (str): IP address for listening.
            listen_port (int): Port for listening.
            quotes_manager (QuotesManager): Instance to manage quotes.
            event_handler (callable): Optional callback for structured events.
        """
        self.server_addr = server_addr
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.addr = (self.listen_ip, self.listen_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.addr)
        self.running = False
        self.quotes_manager = quotes_manager
        self.event_handler = event_handler

    def emit_event(self, event):
        if self.event_handler is not None:
            self.event_handler(event)

    def emit_events(self, events):
        for event in events:
            self.emit_event(event)

    def connect(self):
        """
        Sends a subscription request of listening address to the server
        """
        self.socket.sendto(fxp_bytes_subscriber.marshal_sub_request
                           (self.listen_ip, self.listen_port), self.server_addr)
        self.emit_event({
            'type': 'subscription_requested',
            'server_addr': self.server_addr,
            'listen_addr': self.addr,
        })

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
                    events = self.quotes_manager.process_quotes(unprocessed_quotes)
                    self.emit_events(events)
                    # reset the timeout after receiving data
                    self.socket.settimeout(timeout)
            except socket.timeout:
                self.stop_running(
                    reason='timeout',
                    message=f"No incoming messages for {timeout} seconds. Shutting down...",
                    timeout=timeout,
                )
            except socket.error as e:
                self.emit_event({
                    'type': 'subscriber_error',
                    'message': f"Socket error: {e}",
                    'error': str(e),
                })
                self.stop_running(reason='socket_error')
            except Exception as e:
                self.emit_event({
                    'type': 'subscriber_error',
                    'message': f"Error: {e}",
                    'error': str(e),
                })
                self.stop_running(reason='error')

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
        self.emit_event({
            'type': 'subscriber_started',
            'server_addr': self.server_addr,
            'listen_addr': self.addr,
        })

    def stop_running(self, reason='stopped', message=None, timeout=None):
        was_running = self.running
        self.running = False
        try:
            self.socket.close()
        except OSError:
            pass

        if was_running:
            self.emit_event({
                'type': 'subscriber_stopped',
                'reason': reason,
                'message': message,
                'timeout': timeout,
                'server_addr': self.server_addr,
                'listen_addr': self.addr,
            })
