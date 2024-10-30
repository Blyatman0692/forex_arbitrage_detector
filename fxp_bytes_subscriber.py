"""
forex_bytes_subscriber.py
Junwen Zheng
Version: Oct 30, 2024 -- added comments for submission

This module provides functionality for encoding and decoding forex subscription requests
and forex quote messages for UDP communication.
"""
import socket
import struct
import datetime
import fxp_bytes


def marshal_sub_request(ip, port):
    """
    Marshals the subscription request by encoding the IP address and port into a binary format.

    This function converts the provided IP address and port into a 6-byte binary message
    format, suitable for sending as a subscription request over UDP.

    :param:
        ip (str): The IP address to encode in the subscription request.
        port (int): The port number to encode in the subscription request.

    :return:
        bytes: A 6-byte binary message combining the IP and port.

    :raises:
        ValueError: If the IP address is invalid or the port number is outside the 0-65535 range.
    """
    try:
        # Convert IP address to a 4-byte representation
        ip_encoded = socket.inet_aton(ip)
    except socket.error as e:
        raise ValueError(f"Invalid IP address: {ip}") from e

        # Convert port number to a 2-byte representation (big-endian)
    if not (0 <= port <= 65535):
        raise ValueError(f"Invalid port number: {port}")
    port_encoded = struct.pack('!H', port)

    # Combine the IP address and port into a single message
    encoded_request = ip_encoded + port_encoded

    return encoded_request


def unmarshal_quotes(msg):
    """
    Unmarshal a message containing multiple forex quotes into a list of readable quotes.

    This function processes a binary message containing one or more 32-byte forex quotes.
    Each quote includes currency pairs, price, and a timestamp, which are extracted and
    decoded into a readable dictionary format.

    :param:
        msg (bytes): A binary message containing one or more 32-byte forex quotes.

    :return:
        list: A list of dictionaries, each representing a forex quote with 'cross' (currency pair),
              'price' (float), and 'time' (datetime object) fields.

    :raises:
        ValueError: If the message length is not a multiple of 32 bytes.
    """
    if len(msg) % 32 != 0:
        raise ValueError("Incorrect message format!")

    quotes = []
    num_quotes = len(msg) // 32

    for i in range(num_quotes):
        raw = msg[i * 32: (i + 1) * 32]
        currency1 = raw[0: 3].decode('ascii')
        currency2 = raw[3: 6].decode('ascii')
        cross = f"{currency1}/{currency2}"

        price = struct.unpack('<f', raw[6: 10])[0]

        time_in_us = struct.unpack('>Q', raw[10: 18])[0]
        time_in_s = time_in_us // 1000000
        reminder_us = time_in_us % 1000000

        epoch = datetime.datetime(1970, 1, 1)
        timestamp = epoch + datetime.timedelta(seconds=time_in_s, microseconds=reminder_us)

        quote = {
            'cross': cross,
            'price': price,
            'time': timestamp
        }

        quotes.append(quote)

    return quotes


if __name__ == '__main__':
    """
    test main to see if methods are working properly
    """
    quotes = [{'cross': 'GBP/USD', 'price': 9.9900000000, 'time': datetime.datetime(2006,1,2)},
             {'cross': 'USD/JPY', 'price': 108.2755, 'time': datetime.datetime.utcnow()}]
    serialized_msg = fxp_bytes.marshal_message(quotes)
    print(unmarshal_quotes(serialized_msg))
    print(marshal_sub_request('127.0.0.1', 10101))
