# Word Chain Game Client
# Version 1.0 Basic 2-player word chain game
# Author: Alexander, Brandon, Jorie
# Date: 10/9/2025
# Updated: 10/15/2025 - Added countdown timer for player turns

from socket import *
import os
import threading
import time
import sys
import queue

def clear_screen():
    # Clear the terminal screen (Windows/Unix)
    os.system("cls" if os.name == "nt" else "clear")


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
        while True:
            data = sock.recv(1024)
            if not data:
                print("\nConnection closed by server.")
                os._exit(0)
            text = data.decode()
            # Print immediately so messages show even if main thread is blocked on input
            print("\n" + text)
            msg_queue.put(text)
            if "Game over" in text:
                sock.close()
                os._exit(0)

    recv_thread = threading.Thread(target=socket_receiver, args=(clientSocket, message_queue), daemon=True)
    recv_thread.start()

    while True:
        # Wait for the next message from the server (placed by receiver thread)
        message = message_queue.get()
        if message is None:
            break
        clear_screen()
        print(message)
        if "Your turn" in message:
            # Start a simple countdown timer in a daemon thread. If the timer reaches
            # `timeout` seconds before the player enters a word, the thread will send
            # a TimerExpired message to the server.
            timeout_seconds = 10
            response_sent_event = threading.Event()

            # Reserve a status line above the prompt for the timer, then print
            # the prompt on its own line so the timer can update the status line
            # without creating many extra lines.
            print()  # blank line reserved for timer status
            sys.stdout.write("Enter your word: ")
            sys.stdout.flush()

            timer_thread = threading.Thread(target=countdown_timer, args=(clientSocket, response_sent_event, timeout_seconds), daemon=True)
            timer_thread.start()

            # Blocking input; if entered before timeout, send word and set the event so
            # the timer thread doesn't send the timeout message.
            try:
                word = input()
            except (EOFError, KeyboardInterrupt):
                word = ''

            if not response_sent_event.is_set():
                # Checks if the timer has already expired
                clientSocket.send(word.encode())
                response_sent_event.set()
                # Sets the event to stop the timer thread
            else:
                # Timer already expired; ignore late input
                print("Input ignored because time already expired.")
        elif "Enter Your Name" in message:
            try:
                word = input()
            except (EOFError, KeyboardInterrupt):
                word = ''
            clientSocket.send(word.encode())
        elif "Game over" in message or not message:
            break

    clientSocket.close()

client_main()