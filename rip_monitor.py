"""
RIP Routing Monitor - Real-time visualization of RIP routing table updates.
Shows routing information and RIP protocol operations as the system progresses.
"""
import os
import sys
import time
import tempfile
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from network.logging_util import setup_logging, get_logger


def print_header():
    """Print the monitor header."""
    print("\n" + "=" * 100)
    print("🛣️  RIP ROUTING MONITOR - Real-time Routing Protocol Activity".center(100))
    print("=" * 100)
    print("\nMonitoring RIP routing table updates, broadcasts, and peer routes...")
    print("Press Ctrl+C to stop monitoring.\n")


def cleanup_old_files():
    """Clean up all old RIP and heartbeat files from previous runs."""
    try:
        temp_dir = tempfile.gettempdir()
        
        # Remove all heartbeat files
        for hb_file in Path(temp_dir).glob("heartbeat_*.txt"):
            try:
                hb_file.unlink()
            except:
                pass
        
        # Remove all RIP update files
        for rip_file in Path(temp_dir).glob("rip_updates_*.txt"):
            try:
                rip_file.unlink()
            except:
                pass
        
        # Remove all RIP state JSON files
        for rip_json in Path(temp_dir).glob("peer_rip_*.json"):
            try:
                rip_json.unlink()
            except:
                pass
        
        print("✓ Cleaned up old RIP and heartbeat files from previous runs")
    except Exception as e:
        print(f"Warning: Could not clean old files: {e}")



def parse_rip_updates():
    """Parse RIP update files and extract routing information."""
    try:
        temp_dir = tempfile.gettempdir()
        
        # Find all RIP update files
        rip_files = list(Path(temp_dir).glob("rip_updates_*.txt"))
        
        all_updates = {}
        
        for rip_file in rip_files:
            try:
                with open(rip_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        for line in content.split('\n'):
                            if line.strip():
                                try:
                                    update = json.loads(line)
                                    sender_id = update.get('sender_id', 'unknown')
                                    timestamp = update.get('timestamp', '')
                                    routing_table = update.get('routing_table', {})
                                    msg_id = update.get('msg_id', '')
                                    
                                    if sender_id not in all_updates:
                                        all_updates[sender_id] = []
                                    
                                    all_updates[sender_id].append({
                                        'timestamp': timestamp,
                                        'routes': routing_table,
                                        'msg_id': msg_id
                                    })
                                except:
                                    pass
            except:
                pass
        
        return all_updates
    except Exception as e:
        print(f"Error parsing RIP updates: {e}")
        return {}


def get_heartbeat_status():
    """Get heartbeat status of ALL peers (active and disconnected)."""
    try:
        temp_dir = tempfile.gettempdir()
        heartbeat_files = list(Path(temp_dir).glob("heartbeat_*.txt"))
        
        peers = {}
        now = datetime.now()
        
        for hb_file in heartbeat_files:
            try:
                with open(hb_file, 'r', encoding='utf-8') as f:
                    data = json.loads(f.read())
                    user_id = data.get('user_id', 'unknown')
                    user_port = data.get('user_port', '?')
                    timestamp_str = data.get('timestamp', '')
                    is_teacher = data.get('is_teacher', False)
                    
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        response_time = (now - timestamp).total_seconds()
                        # Show as alive if heartbeat < 15 seconds old
                        is_alive = response_time < 15
                    except:
                        response_time = 0
                        is_alive = False
                    
                    # Add ALL peers (both alive and disconnected)
                    peer_type = "👨‍🏫 TEACHER" if is_teacher else "👤 STUDENT"
                    status_icon = "✅" if is_alive else "❌"
                    
                    peers[f"{user_id}:{user_port}"] = {
                        'type': peer_type,
                        'status': status_icon,
                        'response_time': response_time,
                        'alive': is_alive
                    }
            except:
                pass
        
        return peers
    except Exception as e:
        print(f"Error getting heartbeat status: {e}")
        return {}


def display_routing_info(rip_updates, heartbeats):
    """Display comprehensive routing information from all and active peers."""
    print("\n" + "-" * 100)
    print(f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 100)
    
    # Get list of ACTIVE peer IDs (for RIP filtering)
    active_peer_ids = set()
    for peer_key, info in heartbeats.items():
        if info['alive']:
            peer_id = peer_key.split(':')[0]  # Extract user_id from "user_id:port"
            active_peer_ids.add(peer_id)
    
    # Display heartbeat status (ALL peers - active and disconnected)
    if heartbeats:
        # Separate active and disconnected peers
        active_peers = {k: v for k, v in heartbeats.items() if v['alive']}
        disconnected_peers = {k: v for k, v in heartbeats.items() if not v['alive']}
        
        print("\n📡 PEER STATUS:")
        print("─" * 100)
        
        # Show active peers first
        if active_peers:
            print("  ACTIVE PEERS:")
            for peer_id, info in sorted(active_peers.items()):
                print(f"    {info['status']} {info['type']:20} | {peer_id:30} | Response: {info['response_time']:.1f}s")
        
        # Show disconnected peers
        if disconnected_peers:
            print("\n  DISCONNECTED PEERS:")
            for peer_id, info in sorted(disconnected_peers.items()):
                print(f"    {info['status']} {info['type']:20} | {peer_id:30} | Last seen: {info['response_time']:.1f}s ago")
    else:
        print("\n📡 PEER STATUS: No peers recorded (waiting for peers to connect)")
    
    # Display RIP routing tables - ONLY from ACTIVE peers
    if rip_updates:
        print("\n🛣️  RIP ROUTING TABLES (from active peers):")
        print("─" * 100)
        
        for sender_id, updates_list in sorted(rip_updates.items()):
            # ONLY show RIP updates from active peers
            if sender_id not in active_peer_ids:
                continue
            
            if updates_list:
                latest_update = updates_list[-1]
                timestamp = latest_update['timestamp']
                routes = latest_update['routes']
                msg_id = latest_update['msg_id']
                
                try:
                    ts_obj = datetime.fromisoformat(timestamp)
                    time_str = ts_obj.strftime('%H:%M:%S')
                except:
                    time_str = timestamp
                
                print(f"\n  📤 From: {sender_id} | Time: {time_str} | Msg ID: {msg_id}")
                
                if routes:
                    for dest_key, route_info in sorted(routes.items()):
                        # Handle both tuple (next_hop, metric) and list [next_hop, metric] formats
                        if isinstance(route_info, (tuple, list)) and len(route_info) == 2:
                            next_hop, metric = route_info[0], route_info[1]
                            print(f"      → {dest_key:30} via {next_hop:20} (metric: {metric})")
                        else:
                            print(f"      → {dest_key:30} via {route_info} (invalid format)")
                else:
                    print(f"      (No routes in table)")
    else:
        print("\n⏳ Waiting for RIP updates from active peers...")
    
    print("\n" + "-" * 100)


def monitor_rip():
    """Main RIP monitoring loop."""
    setup_logging()
    logger = get_logger('RIP_Monitor')
    
    # Clean up old files from previous runs BEFORE displaying header
    cleanup_old_files()
    
    print_header()
    logger.info("RIP Monitor started - cleaned up old files")
    
    last_display = 0
    display_interval = 3  # Update display every 3 seconds
    
    try:
        while True:
            current_time = time.time()
            
            if current_time - last_display >= display_interval:
                # Get current RIP and heartbeat data
                rip_updates = parse_rip_updates()
                heartbeats = get_heartbeat_status()
                
                # Clear screen (works on Windows and Unix)
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Display header again
                print_header()
                
                # Display current information
                display_routing_info(rip_updates, heartbeats)
                
                last_display = current_time
            
            time.sleep(0.5)  # Check every 500ms, but only display every 3s
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 100)
        print("🛑 RIP Monitor stopped.".center(100))
        print("=" * 100 + "\n")
        logger.info("RIP Monitor stopped by user")
    except Exception as e:
        print(f"\n❌ Error in RIP Monitor: {e}")
        logger.error(f"RIP Monitor error: {e}", exc_info=True)


if __name__ == '__main__':
    monitor_rip()
