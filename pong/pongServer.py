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
WINNING_SCORE = 5


class GameRoom:
    """One independent two-player Pong game."""

    def __init__(self):
        self.lock = threading.Lock()

        self.players = {
            "left": None,
            "right": None
        }

        self.reports = {
            "left": None,
            "right": None
        }

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

        self.ready_event = threading.Event()

        self.play_again = set()
        self.reset_pending = set()

        self.round_number = 1
        self.closed = False

    def game_over(self):
        return (
            self.state["scores"]["left"] >= WINNING_SCORE
            or self.state["scores"]["right"] >= WINNING_SCORE
        )

    def reset_game(self):
        """Reset the game after both players agree."""

        self.state["paddles"] = {
            "left": {"x": 10, "y": 215},
            "right": {"x": 620, "y": 215}
        }

        self.state["ball"] = {
            "x": 320,
            "y": 240,
            "xVel": -5,
            "yVel": 0
        }

        self.state["scores"] = {
            "left": 0,
            "right": 0
        }

        self.reports = {
            "left": None,
            "right": None
        }

        self.reset_pending = {"left", "right"}
        self.play_again.clear()

        self.round_number += 1

        print(f"Starting round {self.round_number}")

    def make_snapshot(self, player):
        """Create a copy of the current game state."""

        reset = player in self.reset_pending

        self.reset_pending.discard(player)

        return {
            "paddles": {
                "left": dict(self.state["paddles"]["left"]),
                "right": dict(self.state["paddles"]["right"])
            },
            "ball": dict(self.state["ball"]),
            "scores": dict(self.state["scores"]),
            "sync": dict(self.state["sync"]),
            "game_over": self.game_over(),
            "round": self.round_number,
            "reset": reset,
            "ready_to_restart": player in self.play_again,
            #inform the client whether an opponent has joined
            "waiting_for_player": not self.ready_event.is_set() 
        }

    def process_update(self, player, message):
        """Process one client update and return its response."""

        with self.lock:

            # Ignore updates from a game that has been closed.
            if self.closed:
                raise ConnectionError("Game room has closed.")

            # Return the current game state without processing
            # gameplay updates until both players have joined
            if not self.ready_event.is_set():
                return self.make_snapshot(player)

            # Store this player's paddle position.
            paddle = message["paddle"]

            self.state["paddles"][player] = {
                "x": int(paddle["x"]),
                "y": int(paddle["y"])
            }

            # Store this player's synchronization counter.
            client_sync = int(message["sync"])

            self.state["sync"][player] = client_sync

            # Save the latest complete report.
            self.reports[player] = message

            # Determine which client has the higher sync counter.
            left_sync = self.state["sync"]["left"]
            right_sync = self.state["sync"]["right"]

            if left_sync > right_sync:
                ahead = "left"

            elif right_sync > left_sync:
                ahead = "right"

            else:
                ahead = player

            # Use the ahead player's ball and scores.
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

            # Accept Play Again only after the game ends.
            action = message.get("action")

            if (
                self.game_over()
                and (
                    action == "play_again"
                    or message.get("play_again") is True
                )
            ):
                self.play_again.add(player)

            # Reset only after BOTH players agree.
            if (
                self.game_over()
                and len(self.play_again) == 2
            ):
                self.reset_game()

            return self.make_snapshot(player)


# =========================================================
# SERVER MANAGEMENT
# =========================================================

manager_lock = threading.Lock()

rooms = set()
waiting_room = None


def send_message(client, message):
    """Send one newline-terminated JSON message."""

    data = json.dumps(message) + "\n"
    client.sendall(data.encode("utf-8"))


def assign_player(client):
    """Assign a client to a new or waiting game room."""

    global waiting_room

    with manager_lock:

        if (
            waiting_room is not None
            and not waiting_room.closed
        ):
            room = waiting_room
            player = "right"

            with room.lock:
                room.players[player] = client

            waiting_room = None

            # Both players have joined.
            room.ready_event.set()

        else:
            room = GameRoom()
            player = "left"

            room.players[player] = client

            rooms.add(room)
            waiting_room = room

    return room, player


def handle_client(client, player, room):
    """Handle one client in its own thread."""

    reader = client.makefile("r", encoding="utf-8")

    print(f"{player} player connected.")

    try:

        while True:

            line = reader.readline()

            if not line:
                break

            message = json.loads(line)

            #stop processing if the game room has closed
            if room.closed:
                break

            # Process and respond to client updates without
            # blocking while waiting for a second player
            snapshot = room.process_update(player, message)

            send_message(client, snapshot)

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        ConnectionError
    ) as error:

        print(f"{player} client error: {error}")

    finally:

        try:
            reader.close()
        except OSError:
            pass

        try:
            client.close()
        except OSError:
            pass

        print(f"{player} player disconnected.")

        global waiting_room

        with manager_lock:

            with room.lock:

                # Do not clear a slot belonging to another client.
                if room.players.get(player) is client:
                    room.players[player] = None

                room.closed = True

                # Wake a client waiting for its opponent.
                room.ready_event.set()

                opponent = (
                    room.players["right"]
                    if player == "left"
                    else room.players["left"]
                )

            rooms.discard(room)

            if waiting_room is room:
                waiting_room = None

        # Disconnect the opponent so it can detect the game ending.
        if opponent is not None:

            try:
                opponent.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                opponent.close()
            except OSError:
                pass


# =========================================================
# MAIN SERVER
# =========================================================

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
    server.listen(socket.SOMAXCONN)

    print("============================================")
    print("         MULTIPLAYER PONG SERVER")
    print("============================================")
    print(f"Server listening on {HOST}:{PORT}")
    print("Waiting for players...")

    try:

        while True:

            client, address = server.accept()

            print(f"New connection from {address}")

            room, player = assign_player(client)

            # This must be sent before the game starts.
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

            threading.Thread(
                target=handle_client,
                args=(client, player, room),
                daemon=True
            ).start()

    except KeyboardInterrupt:

        print("\nShutting down server...")

    finally:

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

                try:
                    client.close()
                except OSError:
                    pass

        server.close()

        print("Server successfully shut down.")


if __name__ == "__main__":
    main()

# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games
