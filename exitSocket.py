from fyers_apiv3.FyersWebsocket import order_ws

access_token = "E3D5D0NFAV:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCcGdXa010ZmE3ZWh1RzhMd0d3STRla2Z0QV9lc1JFaVZ6dWhLcE9RaExYSVZVdktYMFBEVk5UalpOS0V3VVkta19ZUG5TMG56VExHRW9sdEFwSDB1VmtZQlBtRmh0RENNekRzV21fbVBoN0t3ZkpyMD0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiI1MGJhNjIzOWJkOTdiNTI0MDAwZTgyYzk2N2E2ZDY5OGJhMmE0Yjc1YjhmNWUxNDU4YjIzNWZkNCIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWUE0NDA3NyIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzcwMTY1MDAwLCJpYXQiOjE3NzAwODg3MTYsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc3MDA4ODcxNiwic3ViIjoiYWNjZXNzX3Rva2VuIn0.vKTmyXFfz4udwXRTlS79amz_R-FCk2HGC7hRfe83BiU"



def onPosition(message):
    """
    Callback function to handle incoming messages from the FyersDataSocket WebSocket.

    Parameters:
        message (dict): The received message from the WebSocket.

    """
    print("Position Response:", message)


def onerror(message):
    """
    Callback function to handle WebSocket errors.

    Parameters:
        message (dict): The error message received from the WebSocket.


    """
    print("Error:", message)


def onclose(message):
    """
    Callback function to handle WebSocket connection close events.
    """
    print("Connection closed:", message)


def onOrder(message):
    """
    Callback function to handle incoming messages from the FyersDataSocket WebSocket.

    Parameters:
        message (dict): The received message from the WebSocket.

    """
    print("Order Response:", message)


def onopen():
    """
    Callback function to subscribe to data type and symbols upon WebSocket connection.

    """
    # Specify the data type and symbols you want to subscribe to
    data_type = "OnPositions,OnOrders"

    # data_type = "OnOrders"
    # data_type = "OnTrades"
    # data_type = "OnGeneral"
    # data_type = "OnOrders,OnTrades,OnPositions,OnGeneral"

    fyers.subscribe(data_type=data_type)

    # Keep the socket running to receive real-time data
    fyers.keep_running()


# Replace the sample access token with your actual access token obtained from Fyers

# Create a FyersDataSocket instance with the provided parameters
fyers = order_ws.FyersOrderSocket(
    access_token=access_token,  # Your access token for authenticating with the Fyers API.
    write_to_file=False,        # A boolean flag indicating whether to write data to a log file or not.
    log_path="",                # The path to the log file if write_to_file is set to True (empty string means current directory).
    on_connect=onopen,          # Callback function to be executed upon successful WebSocket connection.
    on_close=onclose,           # Callback function to be executed when the WebSocket connection is closed.
    on_error=onerror,           # Callback function to handle any WebSocket errors that may occur.
    on_positions=onPosition,    # Callback function to handle position-related events from the WebSocket.
    on_orders=onOrder    
    
)


# Establish a connection to the Fyers WebSocket
fyers.connect()
