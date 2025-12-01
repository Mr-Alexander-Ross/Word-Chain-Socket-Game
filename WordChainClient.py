# Word Chain Game Client
# Version 1.6 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025     - Initial Version 1.0
# Updated: 11/05/2025 - Added countdown timer for player turns
# Updated: 11/19/2025 - Added Score Tracking through WordChainRecords.txt
# Updated: 11/20/2025 - Added rematch prompt with timeout
#                     - Added input timeout handling for rematch prompt
#                     - Improved terminal output formatting
#                     - Refactored input with timeout to use threading for better UX
# UpdatedL 11/30/2025 - Added high scores display after game over
# Updated: 11/30/2025 - Added ASCII Art throughout the client

from socket import *
import os
import threading
import time
import sys
import queue

def ascii_title():
    print(r"""+o==o--o==o--o==o--o==o--o==o--o==o==o+
||          WORD CHAIN GAME          ||
+o==o--o==o--o==o--o==o--o==o--o==o==o+""")

def round_count(n: int) -> str:
    return f"[& Round {n} &]"

def your_turn_count(n: int) -> str:
    return f"[Turn {n}]"
    
def banner_win():
    print(r"""+------------------------------+
|   GAME OVER! YOU WIN!       |
|            \o/              |
|             |    🏆         |
|            / \              |
+------------------------------+""")

def banner_lose():
    print(r"""+------------------------------+
|   GAME OVER! YOU LOSE!      |
|           x_x               |
|           /|\      💀       |
|           / \               |
+------------------------------+""")

def clear_screen():
    # Clear the terminal screen (Windows/Unix)
    os.system("cls" if os.name == "nt" else "clear")

def input_with_timeout(prompt, timeout_seconds):
    """Prompt the user and wait up to `timeout_seconds` for input.
    Returns the string response (stripped) or None on timeout.
    This uses a background thread to perform blocking input() so we can
    update a per-second countdown in the main thread.
    """
    q = queue.Queue()

    def reader(queue_):
        try:
            line = input()
        except Exception:
            line = ''
        queue_.put(line)

    # Print the prompt (caller usually already wrote it) but ensure flush
    sys.stdout.flush()

    t = threading.Thread(target=reader, args=(q,), daemon=True)
    t.start()

    # Per-second countdown display above the prompt
    for remaining in range(timeout_seconds, 0, -1):
        try:
            # Try to get input with 1s granularity so we can update the countdown
            line = q.get(timeout=1)
            # Clear status line before returning so no countdown text lingers
            try:
                clear_status_line()
            except Exception:
                pass
            return line.strip()
        except queue.Empty:
            # Update status line showing remaining seconds
            try:
                sys.stdout.write('\x1b[s')
                sys.stdout.write('\x1b[1A')
                sys.stdout.write('\x1b[1G')
                sys.stdout.write('\x1b[2K')
                sys.stdout.write(f"Rematch answer required: {remaining-1:2d}s")
                sys.stdout.write('\x1b[u')
                sys.stdout.flush()
            except Exception:
                # fallback: print a short line
                print(f"Rematch answer required: {remaining-1:2d}s")
            continue

    # timed out - clear status line before returning
    try:
        clear_status_line()
    except Exception:
        pass
    return None

def clear_status_line():
    """Clear the reserved timer/status line above the prompt using ANSI if
    available. Falls back to printing a blank line.
    """
    try:
        # move up one line, move to column 1 and clear it
        sys.stdout.write('\x1b[1A')
        sys.stdout.write('\x1b[1G')
        sys.stdout.write('\x1b[2K')
        sys.stdout.flush()
    except Exception:
        # fallback: print a blank line (may not remove the old text)
        print()

def countdown_timer(client_socket, response_event, timeout_seconds):
    """Countdown timer that sends 'TimerExpired' to the server socket if
    `response_event` isn't set before `timeout_seconds` elapse. Prints a
    simple per-second countdown to stdout.
    """
    # Loop once per second, updating the status line each tick.
    # If response_event is set by the main thread (player responded) the
    # timer exits early. If the timer reaches zero it sends a
    # "TimerExpired" message to the server and sets the event itself so
    # that the main thread knows the timeout already occurred.
    for remaining in range(timeout_seconds, 0, -1):
        if response_event.is_set():
            # Stop timer if response received
            return
        # Try to update a single status line above the prompt using ANSI
        # save/restore cursor. If the terminal doesn't support it, fall back
        # to printing a line (less pretty).
        try:
            # save cursor, move up 1, go to column 1, clear line, print status in
            # a fixed position (no newline), then restore cursor so the user's
            # typing position is unchanged.
            sys.stdout.write('\x1b[s')      # save cursor
            sys.stdout.write('\x1b[1A')     # move up one line (the reserved status line)
            sys.stdout.write('\x1b[1G')     # move to column 1
            sys.stdout.write('\x1b[2K')     # clear entire line
            # Write the status without newline so we don't affect the input line
            sys.stdout.write(f"Time left: {remaining:2d}s")
            sys.stdout.write('\x1b[u')      # restore cursor
            sys.stdout.flush()
        except Exception:
            # Fallback: simple print (will add lines)
            print(f"Time left: {remaining:2d}s")
        # Wait one second between updates
        time.sleep(1)

    if not response_event.is_set():
        # Timer reached zero and nobody responded: notify server.
        print("\nTime expired! Sending timer expired to server.")
        client_socket.send("TimerExpired".encode())
        response_event.set()
        # Clear the reserved status line so it doesn't show a stale timer.
        try:
            sys.stdout.write('\x1b[1A')
            sys.stdout.write('\x1b[1G')
            sys.stdout.write('\x1b[2K')
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stdout.write('\x1b[1A')
            sys.stdout.write('\x1b[2K')
            sys.stdout.flush()
        except Exception:
            pass

def client_main():
    serverIP = "localhost"
    serverPort = 12005
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverIP, serverPort))

    # Start a background thread to receive messages and put them into a queue.
    message_queue = queue.Queue()

    def socket_receiver(sock, msg_queue):
        # Receiver only handles networking: receive data and enqueue messages.
        # The main loop is responsible for all terminal output (printing).
        while True:
            data = sock.recv(1024)
            if not data:
                # Socket closed by server. Put a sentinel so the main loop
                # can process any remaining queued messages (e.g. final
                # "Thanks for playing" text) and then exit cleanly.
                try:
                    msg_queue.put(None)
                except Exception:
                    pass
                return
            text = data.decode()
            msg_queue.put(text)

    recv_thread = threading.Thread(target=socket_receiver, args=(clientSocket, message_queue), daemon=True)
    recv_thread.start()
    clear_screen()
    ascii_title()
    print("Connected to Word Chain server. Awaiting Game Start...")
    current_round = 1
    current_turn = 1
    my_count = 1
    while True:
        # Wait for the next message from the server (placed by receiver thread)
        message = message_queue.get()
        if message is None:
            break
        # Clear screen when a new game starts or a word is accepted so the
        # player sees a clean prompt. Keep other messages visible for context.
        if ("Accepted" in message) or ("Invalid word" in message) or ("Player used" in message) or  ("Game start" in message) or ("Starting new game" in message):
            clear_screen()

        for line in message.splitlines():
            if line.strip().startswith("Your turn"):
                continue
            if line.startswith("Round "):
                try:
                    current_round = int(line.split()[1])
                except Exception:
                    current_round = max(1, current_round)
                my_count = 1
                continue

            if line.startswith("Turn "):
                try:
                    current_turn = int(line.split()[1])
                except Exception:
                    current_turn = max(0, current_turn)
                continue

            if line.startswith("Accepted"):
                my_count += 1

            if "Game over! You won!" in line:
                banner_win()
                continue

            if "Game over! You lost." in line:
                banner_lose()
                continue

            print(line)
        if "Your turn" in message:
            # Use input_with_timeout for turn input so timeout handling and the
            # per-second countdown are centralized in one helper.

            timeout_seconds = 10

            # Reserve a status line and show prompt
            print()  # blank line reserved for timer/status
            print(round_count(current_round))
            print(your_turn_count(my_count))
            print("+--------------------+")
            print("|  >> YOUR TURN <<   |")
            print("+--------------------+")
            print()
            sys.stdout.write("Enter your word: ")
            sys.stdout.flush()

            # Get input with timeout. input_with_timeout returns the string or
            # None on timeout.
            word = input_with_timeout("", timeout_seconds)

            if word is None:
                # Timed out
                print("\nTime expired! Sending timer expired to server.")
                try:
                    clientSocket.send("TimerExpired".encode())
                except Exception:
                    pass
            else:
                word = word.strip()
                if word == "":
                    # Player intentionally (or accidentally) sent an empty word.
                    # Send a newline so the server receives bytes that decode
                    # to an empty string (server handles empty submissions).
                    try:
                        clientSocket.send("\n".encode())
                    except Exception:
                        pass
                else:
                    try:
                        clientSocket.send(word.encode())
                    except Exception:
                        pass
        elif "Rematch?" in message:
            # Handle rematch prompt (no timer for this prompt, user has more time)
            #print()  # blank line
            #print(message)
            sys.stdout.write("Enter your response (yes/no): ")
            sys.stdout.flush()

            # Give the user a limited time to answer the rematch prompt. If
            # they don't answer in time we send 'no' and exit the client.
            rematch_timeout = 15
            answer = input_with_timeout("", rematch_timeout)
            if answer is None:
                print("\nNo rematch response entered in time. Sending 'no' and exiting.")
                try:
                    clientSocket.send("no".encode())
                except Exception:
                    pass
                try:
                    clientSocket.close()
                except Exception:
                    pass
                # Exit the client application
                return

            response = answer.strip().lower()
            if response == '':
                response = 'no'

            try:
                clientSocket.send(response.encode())
            except Exception:
                pass
            print(f"Sent rematch response: {response}")
        elif "Please enter your name for the record" in message:
            # Server is asking for player name to store in records
            # Message is already printed by the main loop, just get input
            try:
                name = input()
            except (EOFError, KeyboardInterrupt):
                name = "Anonymous"
            try:
                clientSocket.send(name.encode())
            except Exception:
                pass
        elif "Thanks for playing" in message or not message:
            print("Game session ended.")
            break

    clientSocket.close()

client_main()