import time
import datetime
import subprocess
import os
import sys

# Active window (BDT): 9:00 PM (21:00) to 1:00 PM (13:00) next day
ACTIVE_START_HOUR = 21  # 9:00 PM BDT
ACTIVE_END_HOUR = 13    # 1:00 PM BDT
INTERVAL_SECONDS = 30   # Scrape frequency during active hours
INACTIVE_SLEEP_SECONDS = 300  # 5 minutes sleep during inactive hours

def get_bdt_time():
    """
    Returns the current time converted to Bangladesh Time (BDT = UTC + 6 hours).
    """
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    return utc_now + datetime.timedelta(hours=6)

def is_in_active_window(bdt_time):
    """
    Returns True if the given BDT time is within the active scraping hours.
    """
    hour = bdt_time.hour
    return hour >= ACTIVE_START_HOUR or hour < ACTIVE_END_HOUR

def run_script(script_name):
    """
    Runs a python script as a subprocess and logs output.
    """
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Running {script_name}...")
    try:
        # Using sys.executable to run with the same Python interpreter
        result = subprocess.run([sys.executable, script_name], capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing {script_name}: {e}")
        print("Subprocess stderr:")
        print(e.stderr)
        return False

def check_and_push_git():
    """
    Checks if there are modifications in the scraped files and pushes them to GitHub.
    """
    try:
        # 1. Check git status to see if any tracked files changed
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        files_to_push = ["all_standings.json", "all_matches.json", "bracket_tree.json", "data.json", "index.html"]
        has_changes = False
        
        for line in status.stdout.splitlines():
            # Lines starting with ' M' or 'M ' indicate modifications
            for f in files_to_push:
                if f in line or f" {f}" in line:
                    has_changes = True
                    break
        
        if has_changes:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Standings/match changes detected. Preparing commit...")
            # Add files
            subprocess.run(["git", "add", "-f"] + files_to_push, check=True)
            
            # Commit
            bdt_now = get_bdt_time()
            commit_msg = f"Auto-update live data: {bdt_now.strftime('%Y-%m-%d %I:%M:%S %p')} (BDT)"
            subprocess.run(["git", "-c", "core.autocrlf=true", "commit", "-m", commit_msg], check=True)
            
            # Push
            print("Pushing updates to GitHub...")
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("Push completed successfully!")
        else:
            print("No changes in standings or matches. Skipping git push.")
            
    except Exception as git_err:
        print(f"Git push operation failed: {git_err}")


def main():
    print("==========================================================")
    print("FIFA World Cup 2026 Dashboard Local Background Scheduler")
    print(f"BDT Active Hours: {ACTIVE_START_HOUR}:00 BDT to {ACTIVE_END_HOUR}:00 BDT (9 PM to 1 PM)")
    print(f"Interval: Every {INTERVAL_SECONDS} seconds during active window")
    print("==========================================================\n")
    
    startup_run = True
    
    while True:
        try:
            bdt_now = get_bdt_time()
            bdt_str = bdt_now.strftime('%Y-%m-%d %I:%M:%S %p')
            
            if startup_run or is_in_active_window(bdt_now):
                if startup_run:
                    print(f"\n--- Initial Startup Cycle: {bdt_str} (BDT) ---")
                else:
                    print(f"\n--- Cycle Start: {bdt_str} (BDT) [ACTIVE WINDOW] ---")
                start_time = time.time()
                
                # Execute the scraper/builder steps
                success = True
                for script in ["scrape_standings.py", "scrape_bracket.py", "scrape_bracket_tree.py", "dump_data.py", "build_static.py"]:
                    if not run_script(script):
                        success = False
                        # We still continue even if one script fails to try and recover others
                
                if success:
                    check_and_push_git()
                else:
                    print("Skipping git push check due to step execution errors.")
                
                if startup_run:
                    startup_run = False
                    print("Initial startup cycle finished.")
                
                # Compute elapsed time and sleep for remaining interval
                elapsed = time.time() - start_time
                sleep_time = max(0.1, INTERVAL_SECONDS - elapsed)
                print(f"Cycle finished. Elapsed time: {elapsed:.2f}s. Sleeping for {sleep_time:.2f}s...")
                time.sleep(sleep_time)
                
            else:
                # Outside active hours, sleep longer
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Current BDT: {bdt_str}. Outside active hours. Sleeping for {INACTIVE_SLEEP_SECONDS // 60} minutes...")
                time.sleep(INACTIVE_SLEEP_SECONDS)
                
        except KeyboardInterrupt:
            print("\nScheduler stopped by user request. Exiting...")
            break
        except Exception as loop_err:
            print(f"\nUnexpected error in scheduler loop: {loop_err}")
            print("Sleeping for 10 seconds before retrying...")
            time.sleep(10)

if __name__ == "__main__":
    import socket
    import threading

    def listen_for_shutdown(sock):
        try:
            sock.listen(1)
            while True:
                conn, addr = sock.accept()
                msg = conn.recv(1024)
                if msg == b"shutdown":
                    print("\n[Scheduler] Received shutdown signal from new instance. Exiting...")
                    conn.close()
                    os._exit(0)
        except Exception:
            pass

    port = 54321
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.bind(('127.0.0.1', port))
    except socket.error:
        # Port is already in use, try to shut down the existing instance
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('127.0.0.1', port))
            client.sendall(b"shutdown")
            client.close()
            print("[Scheduler] Sent shutdown signal to already running instance.")
        except Exception:
            pass
        
        # Wait and retry binding to the port
        for _ in range(15):
            time.sleep(0.2)
            try:
                lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                lock_socket.bind(('127.0.0.1', port))
                break
            except socket.error:
                continue
        else:
            print("[Scheduler] Failed to acquire scheduler lock. Exiting...")
            sys.exit(0)

    # Start a daemon thread to listen for shutdown requests
    t = threading.Thread(target=listen_for_shutdown, args=(lock_socket,), daemon=True)
    t.start()

    main()

