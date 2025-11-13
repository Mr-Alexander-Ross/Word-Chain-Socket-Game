# Word Chain Game Server
# Version 1.0 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025
# Updated: 10/15/2025 - Updated to handle timer expiration from clients



from socket import *
from _thread import *
import os
import enchant  # Add PyEnchant

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
    serverSocket.listen(2)
    print("Word Chain server is ready!")

    dictionary = load_dictionary()

    while True:
        print("Waiting for two players to connect...")
        player1, addr1 = serverSocket.accept()
        print("Player 1 connected.")
        player2, addr2 = serverSocket.accept()
        print("Player 2 connected.")
        start_new_thread(word_chain_thread, (player1, player2, dictionary))

server_main()