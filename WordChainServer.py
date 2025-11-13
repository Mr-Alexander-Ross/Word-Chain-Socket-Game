# Word Chain Game Server
# Version 1.0 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025
# Updated: 10/15/2025 - Updated to handle timer expiration from clients



from socket import *
from _thread import *
import threading
import os
import enchant  # Add PyEnchant

# Simple lobby management for pairing players before starting a game
class Lobby:
    def __init__(self, name, owner_name, owner_sock, max_players=2):
        self.name = name
        self.owner_name = owner_name
        self.players = [(owner_name, owner_sock)]
        self.lock = threading.Lock()
        self.max_players = max_players
        self.state = "waiting"

# Global lobby registry and lock
lobbies = {}
lobbies_lock = threading.Lock()

def load_dictionary():
    # Use PyEnchant English dictionary
    return enchant.Dict("en_US")

def word_chain_thread(player1, player2, dictionary):
    print("Starting Word Chain game thread")
    used_words = []
    current_player = player1
    other_player = player2
    last_letter = None

    # Start the game
    player1.send("Welcome to Word Chain! You are Player 1.\n".encode())
    player2.send("Welcome to Word Chain! You are Player 2.\n".encode())
    player1.send("Game starts! Please enter the first word:\n".encode())
    player2.send("Waiting for Player 1 to start...\n".encode())

    while True:
        # Ask current player for a word
        current_player.send("Your turn.\n".encode())
        word = current_player.recv(1024).decode().strip().lower()
        
        if word == "timerexpired":
            # Handle timer expiration
            current_player.send("Time expired!\n".encode())
            other_player.send("Opponent's time expired!\n".encode())
            break

        # Check if word is valid using PyEnchant
        if not dictionary.check(word):
            current_player.send(f"{word} is an Invalid word.\n".encode())
            break
        if word in used_words:
            current_player.send(f"{word} already used.\n".encode())
            break
        if last_letter and word[0] != last_letter:
            current_player.send(f"Word must start with '{last_letter}'.\n".encode())
            break

        # Word is valid
        used_words.append(word)
        last_letter = word[-1]
        current_player.send(f"Accepted!\n".encode())
        other_player.send(f"Player used '{word}'.\n".encode())

        # Swap players
        current_player, other_player = other_player, current_player
    current_player.send("Game over! You lost.\n".encode())
    other_player.send("Game over! You won!\n".encode())

def server_main():
    serverPort = 12005
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.bind(("", serverPort))
    serverSocket.listen(50)
    print("Word Chain server is ready!")

    dictionary = load_dictionary()

    def client_handler(client_sock, addr):
        """Handle lobby commands from a single connected client."""
        try:
            while True:
                data = client_sock.recv(1024)
                if not data:
                    return
                msg = data.decode().strip()
                if not msg:
                    continue
                parts = msg.split(' ', 2)
                cmd = parts[0]
                if cmd == 'LIST_LOBBIES':
                    # Build a pipe-separated list: name,owner,count
                    with lobbies_lock:
                        entries = []
                        for name, lob in lobbies.items():
                            entries.append(f"{name},{lob.owner_name},{len(lob.players)}")
                    payload = '|'.join(entries)
                    client_sock.send(f"LOBBY_LIST {payload}\n".encode())
                elif cmd == 'CREATE_LOBBY' and len(parts) >= 3:
                    lobby_name, player_name = parts[1], parts[2]
                    with lobbies_lock:
                        if lobby_name in lobbies:
                            client_sock.send(f"LOBBY_JOIN_FAILED NameTaken\n".encode())
                        else:
                            lobbies[lobby_name] = Lobby(lobby_name, player_name, client_sock)
                            client_sock.send(f"LOBBY_CREATED {lobby_name}\n".encode())
                elif cmd == 'JOIN_LOBBY' and len(parts) >= 3:
                    lobby_name, player_name = parts[1], parts[2]
                    with lobbies_lock:
                        if lobby_name not in lobbies:
                            client_sock.send(f"LOBBY_JOIN_FAILED NoSuchLobby\n".encode())
                            continue
                        lobby = lobbies[lobby_name]
                    # operate on lobby under its lock
                    with lobby.lock:
                        if lobby.state != 'waiting' or len(lobby.players) >= lobby.max_players:
                            client_sock.send(f"LOBBY_JOIN_FAILED Full\n".encode())
                            continue
                        lobby.players.append((player_name, client_sock))
                        # notify the joining client
                        client_sock.send(f"LOBBY_JOINED {lobby_name}\n".encode())
                        # notify existing players
                        for pname, psock in lobby.players:
                            if psock != client_sock:
                                try:
                                    psock.send(f"INFO {player_name} joined {lobby_name}\n".encode())
                                except Exception:
                                    pass
                        # If lobby is full, start the game
                        if len(lobby.players) == lobby.max_players:
                            lobby.state = 'in-game'
                            # extract sockets
                            p1_name, p1_sock = lobby.players[0]
                            p2_name, p2_sock = lobby.players[1]
                            # remove lobby from registry
                            with lobbies_lock:
                                if lobby_name in lobbies:
                                    del lobbies[lobby_name]
                            # notify players and start game thread
                            try:
                                p1_sock.send(f"START_GAME {lobby_name}\n".encode())
                                p2_sock.send(f"START_GAME {lobby_name}\n".encode())
                            except Exception:
                                pass
                            start_new_thread(word_chain_thread, (p1_sock, p2_sock, dictionary))
                elif cmd == 'LEAVE_LOBBY' and len(parts) >= 3:
                    lobby_name, player_name = parts[1], parts[2]
                    with lobbies_lock:
                        if lobby_name not in lobbies:
                            continue
                        lobby = lobbies[lobby_name]
                    with lobby.lock:
                        # remove player if present
                        lobby.players = [(n,s) for (n,s) in lobby.players if s != client_sock]
                        if len(lobby.players) == 0:
                            with lobbies_lock:
                                if lobby_name in lobbies:
                                    del lobbies[lobby_name]
                else:
                    # Unknown command - echo or ignore
                    client_sock.send(f"ERROR UnknownCommand {msg}\n".encode())
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    # Accept clients and start handler threads
    while True:
        print("Waiting for a player to connect...")
        client_sock, addr = serverSocket.accept()
        print(f"Player connected from {addr}.")
        start_new_thread(client_handler, (client_sock, addr))

server_main()