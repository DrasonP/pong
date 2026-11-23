# =================================================================================================
# Contributing Authors:	    Drason Swihart
#                           Paola Martinez
#                           Robert Pike
# Email Addresses:          dpsw224@uky.edu
#                           paola.mar@uky.edu
#                           rfpi223@uky.edu
# Date:                     10/28/2026
# Purpose:                  Server code:    - Supports unlimited client connections
#                                           - Assigns clients to independent two-player games
#                                           - Assigns left and right paddles
#                                           - Tracks paddle positions, ball position, velocity, and scores
#                                           - Synchronizes clients using their sync counters
#                                           - Handles client disconnections
#                                           - Provides a framework for a Play Again feature
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import socket
import threading
import json

HOST = "0.0.0.0"
PORT = 5000

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480


# game room to support multiple client connections
class GameRoom:
    """
    Represents one independent two-player Pong game.

    Each room contains:
        - One left player
        - One right player
        - Both paddle positions
        - Ball position and velocity
        - Both player scores
        - Synchronization counters
    """

    def __init__(self):

        self.lock = threading.Lock()

        # Connected players
        self.players = {
            "left": None,
            "right": None
        }

        # Latest game state reported by each player
        self.reports = {
            "left": None,
            "right": None
        }

        # Shared game state
        self.state = {
            "paddles": {
                "left": {"x": 10, "y": 215},
                "right": {"x": 620, "y": 215}
            },

            "ball": {
                "x": 320,
                "y": 240,
                "xVel": -5,
                "yVel": 0
            },

            "scores": {
                "left": 0,
                "right": 0
            },

            "sync": {
                "left": 0,
                "right": 0
            }
        }

        # Signals when both players have connected.
        self.ready_event = threading.Event()

        # Play Again tracking
        self.play_again = set()

        # Players who still need to receive a reset notification
        self.reset_pending = set()

        # Current game number
        self.round_number = 1

        # Indicates whether the room has been closed
        self.closed = False


  # process client update
    def process_update(self, player, message):
        """
        Receives a game update from one client.

        Updates:
            - Player's paddle position
            - Player's synchronization counter
            - Player's reported ball position
            - Player's reported scores

        Uses the client with the higher sync counter as the
        reference for ball position and scores.
        """

        with self.lock:

            # Update this player's paddle position
            paddle = message["paddle"]

            self.state["paddles"][player] = {
                "x": int(paddle["x"]),
                "y": int(paddle["y"])
            }

            # Update synchronization counter
            client_sync = int(message["sync"])

            self.state["sync"][player] = client_sync

            # Save the complete report from this client
            self.reports[player] = message

            left_sync = self.state["sync"]["left"]
            right_sync = self.state["sync"]["right"]

            # Determine which client is ahead
            if left_sync > right_sync:
                ahead = "left"

            elif right_sync > left_sync:
                ahead = "right"

            else:
                # If counters match, use the newest report.
                ahead = player

            # Use the ahead player's ball and score
            report = self.reports[ahead]

            if report is not None:

                ball = report["ball"]
                scores = report["scores"]

                self.state["ball"] = {
                    "x": int(ball["x"]),
                    "y": int(ball["y"]),
                    "xVel": int(ball["xVel"]),
                    "yVel": int(ball["yVel"])
                }

                self.state["scores"] = {
                    "left": int(scores["left"]),
                    "right": int(scores["right"])
                }

            # Check for Play Again request

            if (message.get("action") == "play_again"
                    or message.get("play_again") is True):

                self.play_again.add(player)


            # Reset game when BOTH players agree
            if len(self.play_again) == 2:

                self.reset_game()

            # Create a snapshot for this client
            snapshot = self.make_snapshot(player)

            return snapshot, ahead, left_sync, right_sync

    # CREATE GAME STATE SNAPSHOT
    def make_snapshot(self, player):
        """
        Creates a consistent copy of the shared game state.
        """

        reset = player in self.reset_pending

        # This player has now received the reset notification.
        self.reset_pending.discard(player)

        return {
            "paddles": {
                "left": dict(self.state["paddles"]["left"]),
                "right": dict(self.state["paddles"]["right"])
            },

            "ball": dict(self.state["ball"]),

            "scores": dict(self.state["scores"]),

            "sync": dict(self.state["sync"]),

            # Additional fields for future client functionality
            "game_over": (
                self.state["scores"]["left"] > 4
                or self.state["scores"]["right"] > 4
            ),

            "round": self.round_number,

            "reset": reset,

            "ready_to_restart": (
                player in self.play_again
            )
        }

    # RESET GAME
    def reset_game(self):
        """
        Resets the game after both players select Play Again.

        Synchronization counters are preserved so that clients
        do not have to restart their counters.
        """

        # Reset paddle positions
        self.state["paddles"] = {
            "left": {"x": 10, "y": 215},
            "right": {"x": 620, "y": 215}
        }

        # Reset ball position and velocity
        self.state["ball"] = {
            "x": 320,
            "y": 240,
            "xVel": -5,
            "yVel": 0
        }

        # Reset scores
        self.state["scores"] = {
            "left": 0,
            "right": 0
        }

        # Remove old reports so an old game state cannot
        # immediately overwrite the newly reset game.
        self.reports = {
            "left": None,
            "right": None
        }

        # Both clients must receive a reset notification.
        self.reset_pending = {"left", "right"}

        # Clear Play Again requests for the next round.
        self.play_again.clear()

        self.round_number += 1

        print(f"Game reset! Starting round {self.round_number}")


# SERVER MANAGEMENT

# Protects the list of active rooms and player assignments.
manager_lock = threading.Lock()

# All currently active game rooms.
rooms = set()

# Room currently waiting for its second player.
waiting_room = None


# SEND JSON MESSAGE
def send_message(client, message):
    """
    Sends a JSON message to a client.

    A newline marks the end of each message so the client
    can read messages using readline().
    """

    data = json.dumps(message) + "\n"

    client.sendall(data.encode("utf-8"))


# HANDLE CLIENT
def handle_client(client, player, room):
    """
    Handles communication with one connected client.

    Each client gets its own thread.

    The function:
        1. Receives the client's game update.
        2. Updates the shared game state.
        3. Determines which client is ahead.
        4. Sends the latest game state back to that client.
        5. Repeats until the client disconnects.
    """

    reader = client.makefile("r", encoding="utf-8")

    print(f"{player} player connected to game room.")

    try:

        while True:

            # Receive client update

            line = reader.readline()

            if not line:
                break

            message = json.loads(line)
            # Wait until both players have joined

            # The first player can connect and send an update
            # before the second player joins.
            #
            # We wait here rather than sending incomplete
            # game information to the first client.

            room.ready_event.wait()

            if room.closed:
                break

            # Process update and create snapshot
            snapshot, ahead, left_sync, right_sync = (
                room.process_update(player, message)
            )

            # Synchronization information-

            if left_sync != right_sync:

                print(
                    f"Game synchronization: "
                    f"left={left_sync}, "
                    f"right={right_sync}. "
                    f"Using {ahead} player's ball and score."
                )

            # Send updated state to this client

            # IMPORTANT:
            # Each client receives exactly one response for
            # each update it sends.
            #
            # Sending to both clients every time either client
            # updates would create extra messages in the
            # clients' incoming streams.

            send_message(client, snapshot)

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError
    ) as error:

        print(f"{player} client error: {error}")

    finally:

        reader.close()
        client.close()

        print(f"{player} player disconnected.")

        # Clean up disconnected player and game room

        global waiting_room

        with manager_lock:

            with room.lock:

                if room.players.get(player) is client:

                    room.players[player] = None

                room.closed = True

                # Wake any thread waiting for the second player.
                room.ready_event.set()

                # Find the remaining player, if one exists.
                opponent = (
                    room.players["right"]
                    if player == "left"
                    else room.players["left"]
                )

            rooms.discard(room)

            if waiting_room is room:
                waiting_room = None

        # Disconnect the opponent so their client can
        # detect that the game has ended.
        if opponent is not None:

            try:
                opponent.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


# ASSIGN NEW CLIENT TO A GAME

def assign_player(client):
    """
    Assigns a newly connected client to a game.

    If a room is waiting for a player:
        Assign the new client to the right paddle.

    Otherwise:
        Create a new room and assign the client to the left paddle.
    """

    global waiting_room

    with manager_lock:

        # Check whether an existing room needs another player
        if waiting_room is not None and not waiting_room.closed:

            room = waiting_room

            player = "right"

            room.players[player] = client

            # Both players are now connected.
            waiting_room = None

            room.ready_event.set()

        else:

            # Create a new game room
            room = GameRoom()

            player = "left"

            room.players[player] = client

            rooms.add(room)

            waiting_room = room

    return room, player


# MAIN SERVER
def main():

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind((HOST, PORT))

    # Allow a large number of pending connections.
    server.listen(socket.SOMAXCONN)

    print("============================================")
    print("         MULTIPLAYER PONG SERVER")
    print("============================================")
    print(f"Server listening on {HOST}:{PORT}")
    print("Waiting for players...")
    print()

    try:

        while True:

            # Accept a new connection

            client, address = server.accept()

            print(f"New connection from {address}")

            # Assign player to a game
            room, player = assign_player(client)
          
            # Send initial configuration
            configuration = {
                "screen_width": SCREEN_WIDTH,
                "screen_height": SCREEN_HEIGHT,
                "player_paddle": player
            }

            try:

                send_message(client, configuration)

            except OSError:

                print("Could not initialize client connection.")

                client.close()

                continue

            print(
                f"Assigned {player} player. "
                f"Active game rooms: {len(rooms)}"
            )

            # Start a separate thread for this client
            threading.Thread(
                target=handle_client,
                args=(client, player, room),
                daemon=True
            ).start()

    except KeyboardInterrupt:

        print("\nShutting down server...")

    finally:

        # Disconnect all remaining players
        with manager_lock:

            active_rooms = list(rooms)

            rooms.clear()

            waiting_room = None

        for room in active_rooms:

            with room.lock:

                room.closed = True

                room.ready_event.set()

                connected_players = [
                    client
                    for client in room.players.values()
                    if client is not None
                ]

            for client in connected_players:

                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

                client.close()

        server.close()

        print("Server successfully shut down.")


# PROGRAM ENTRY POINT

if __name__ == "__main__":
    main()
# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games
