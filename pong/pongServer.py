# =================================================================================================
# Contributing Authors:	    Drason Swihart
#                           Paola Martinez
#                           Robert Pike
# Email Addresses:          dpsw224@uky.edu
#                           paola.mar@uky.edu
#                           rfpi223@uky.edu
# Date:                     10/28/2026
# Purpose:                  Server code: Accepts both clients · Uses threads · Relays paddle positions, ball location, and score
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import socket
import threading
import json

HOST = "0.0.0.0"
PORT = 5000

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480

# Protect shared game state because both client threads use it.
lock = threading.Lock()

clients = {}
send_locks = {"left": threading.Lock(), "right": threading.Lock()}
              
state = {
  "paddles": {
      "left": {"x": 10, "y": 215} , 
      "right": {"x": 620, "y": 215}
      }, #matching client paddle info structure
    "ball": {
        "x": 320,
        "y": 240,
        "xVel": -5,
        "yVel": 0
    },
    "scores": {"left": 0, "right": 0},
    "sync": {"left": 0, "right": 0}
}

# Latest complete game state reported by each client
reports = {"left": None, "right": None}

def send_message(client, player, message):
  """Send a JSON message, end with newline"""
  data = json.dumps(message) + "\n"
  with send_locks[player]:
    client.sendall(data.encode("utf-8")) #added encode to convert text into bytes

def make_snapshot():
    """Create a consistent copy of the current game state."""
    return {
        "paddles": {
            "left": dict(state["paddles"]["left"]),
            "right": dict(state["paddles"]["right"])
        },
        "ball": dict(state["ball"]),
        "scores": dict(state["scores"]),
        "sync": dict(state["sync"])
    }

def process_update(player, message):
  """Save an update and choose the state used for resynchronization"""
  with lock:
    # store player's paddle coords
    paddle = message["paddle"]
    state["paddles"][player] = {
      "x": int(paddle["x"]),
      "y": int(paddle["y"])
    }

    #record how many game-loop updates this client has completed
    client_sync = int(message["sync"])
    state["sync"][player] = client_sync

    #save complete report from this client
    reports[player] = message

    left_sync = state["sync"]["left"]
    right_sync = state["sync"]["right"]

    # The client with the larger sync counter is ahead.
    if left_sync > right_sync:
        ahead = "left"
    elif right_sync > left_sync:
        ahead = "right"
    else:
        # When counters match, use the newest report.
        ahead = player

    # Use the ahead client's ball and score as the reference.
    report = reports[ahead]

    if report is not None:
        ball = report["ball"]
        scores = report["scores"]

        state["ball"] = {
            "x": int(ball["x"]),
            "y": int(ball["y"]),
            "xVel": int(ball["xVel"]),
            "yVel": int(ball["yVel"])
        }

        state["scores"] = {
            "left": int(scores["left"]),
            "right": int(scores["right"])
        }
    
            # If both clients have reported, send the higher sync counter
            # to both clients so the lagging client can catch up.
        snapshot = make_snapshot()
    
        return snapshot, ahead, left_sync, right_sync


def handle_client(client, player):
    """Receive updates from one client and relay shared state."""
    reader = client.makefile("r", encoding="utf-8")

    try:
        while True:
            line = reader.readline()

            if not line:
                break

            message = json.loads(line)

            snapshot, ahead, left_sync, right_sync = process_update(
                player, message
            )

            # Log only when the clients have different sync counters.
            if left_sync != right_sync:
                print(
                    f"Out of sync: left={left_sync}, "
                    f"right={right_sync}. "
                    f"Using {ahead} player's ball and score."
                )

            # Send the same snapshot to both connected clients.
            with lock:
                destinations = list(clients.items())

            for destination, destination_socket in destinations:
                try:
                    send_message(
                        destination_socket,
                        destination,
                        snapshot
                    )
                except OSError:
                    print(f"Could not send update to {destination}")

    except (OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"{player} client error: {error}")

    finally:
        reader.close()
        client.close()

        with lock:
            if clients.get(player) is client:
                del clients[player]

        print(f"{player} client disconnected")

# for actual client connection
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server.bind((HOST, PORT))

server.listen(2)

print(f"Server listening on {HOST}:{PORT}")

while True:
    client_socket, address = server.accept()

    clients.append(client_socket)

    player_number = len(clients)

    print(f"Player {player_number} connected from {address}")

    threading.Thread(
        target=handle_client,
        args=(client_socket, player_number),
        daemon=True
    ).start()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(2)

    print(f"Server listening on {HOST}:{PORT}")
    print("Waiting for two players...")

    try:
        for player in ("left", "right"):
            client, address = server.accept()

            with lock:
                clients[player] = client

            # Initial configuration message.
            send_message(client, player, {
                "screen_width": SCREEN_WIDTH,
                "screen_height": SCREEN_HEIGHT,
                "player_paddle": player
            })

            print(f"{player} player connected: {address}")

            threading.Thread(
                target=handle_client,
                args=(client, player),
                daemon=True
            ).start()

        print("Both players connected.")

        while True:
            threading.Event().wait(1)

    except KeyboardInterrupt:
        print("\nShutting down server...")

    finally:
        with lock:
            connected = list(clients.values())
            clients.clear()

        for client in connected:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()

        server.close()


if __name__ == "__main__":
    main()
# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games
