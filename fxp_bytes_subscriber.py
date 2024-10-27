"""
My file
"""
import socket
import struct
import datetime
import fxp_bytes


def marshal_sub_request(ip, port):
    """
    todo: comment
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
    todo: comment
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


# if __name__ == '__main__':
#     quotes = [{'cross': 'GBP/USD', 'price': 9.9900000000, 'time': datetime.datetime(2006,1,2)},
#              {'cross': 'USD/JPY', 'price': 108.2755, 'time': datetime.datetime.utcnow()}]
#     serialized_msg = fxp_bytes.marshal_message(quotes)
#
#     msg = b'AUDUSD\t\xfe??\x00\x06%n\x03\xbc\xf9Q\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00EURUSD\xe4\xda\x8c?\x00\x06%n\x03\xbc\xf9Q\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00USDCHFG\x03\x80?\x00\x06%n\x03\xbc\xf9Q\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00GBPUSD\x88\xf4\x9f?\x00\x06%n\x03\xbc\xf9Q\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00AUDCAD\x15\xaa\x18B\x00\x06%n\x03\xbc\xf9Q\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00CADJPY\x15\xaa\x18C\x00\x06%n\x03\xbc\xf9Q\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
#
#     print(unmarshal_quotes(msg))
