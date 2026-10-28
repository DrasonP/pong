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
  "paddles": {"left": 215, "right": 215},
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

def send_message(client,message):
  """Send a JSON message, end with newline"""
  data = json.dumps(message) + "\n"
  with send_locks[player]:
    client.sendall(data)

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
def main():
  
# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games
