"""
Chat messaging system for P2P election.
Supports broadcast and private messages using file-based communication.
Enhanced with: ACK mechanism, heartbeat-based fault detection, and RIP routing.
"""
import os
import tempfile
import json
import time
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class ChatManager:
    """Manages chat messages through temporary files.
    
    Enhanced features:
    - Reliable delivery with ACK mechanism
    - Heartbeat-based fault detection
    - RIP (Routing Information Protocol) routing
    """
    
    def __init__(self, user_id: str, user_port: int, is_teacher: bool = False):
        self.user_id = user_id
        self.user_port = user_port
        self.is_teacher = is_teacher
        self.temp_dir = tempfile.gettempdir()
        self.last_message_time = datetime.now()
        
        # ACK tracking: msg_id -> (timestamp, acknowledged)
        self.pending_acks: Dict[str, Tuple[datetime, bool]] = {}
        
        # Heartbeat tracking: peer_id -> last_heartbeat_time
        self.peer_heartbeats: Dict[str, datetime] = {}
        
        # Routing table for RIP: destination -> (next_hop, metric/distance)
        self.routing_table: Dict[str, Tuple[str, int]] = {}
        
        # Last RIP update broadcast timestamp
        self.last_rip_update = datetime.now()
        self.rip_update_interval = 30  # seconds
    
    # ==================== ACK MECHANISM ====================
    
    def _get_ack_file(self, msg_id: str) -> str:
        """Get path to ACK file for a message."""
        return os.path.join(self.temp_dir, f"ack_{self.user_port}_{msg_id}.txt")
    
    def _send_ack(self, msg_id: str, sender_id: str) -> bool:
        """Send acknowledgment for a received message."""
        try:
            ack_file = self._get_ack_file(msg_id)
            ack_data = {
                'msg_id': msg_id,
                'sender_id': sender_id,
                'ack_from': self.user_id,
                'timestamp': datetime.now().isoformat()
            }
            with open(ack_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(ack_data))
            return True
        except Exception as e:
            print(f"Error sending ACK for {msg_id}: {e}")
            return False
    
    def _check_ack(self, msg_id: str) -> bool:
        """Check if an ACK has been received for a message."""
        try:
            ack_file = self._get_ack_file(msg_id)
            return os.path.exists(ack_file)
        except Exception as e:
            print(f"Error checking ACK for {msg_id}: {e}")
            return False
    
    def _cleanup_old_acks(self, max_age_seconds: int = 3600):
        """Clean up old ACK files (older than max_age_seconds)."""
        try:
            now = datetime.now()
            for filename in os.listdir(self.temp_dir):
                if filename.startswith(f"ack_{self.user_port}_") and filename.endswith(".txt"):
                    filepath = os.path.join(self.temp_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    if (now - file_time).total_seconds() > max_age_seconds:
                        try:
                            os.remove(filepath)
                        except:
                            pass
        except Exception as e:
            print(f"Error cleaning up ACKs: {e}")
    
    # ==================== HEARTBEAT & FAULT DETECTION ====================
    
    def _get_heartbeat_file(self) -> str:
        """Get path to heartbeat file for this peer."""
        return os.path.join(self.temp_dir, f"heartbeat_{self.user_port}_{self.user_id}.txt")
    
    def send_heartbeat(self) -> bool:
        """Send a heartbeat signal to indicate this peer is alive."""
        try:
            heartbeat_file = self._get_heartbeat_file()
            heartbeat_data = {
                'user_id': self.user_id,
                'user_port': self.user_port,
                'timestamp': datetime.now().isoformat(),
                'is_teacher': self.is_teacher
            }
            with open(heartbeat_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(heartbeat_data))
            return True
        except Exception as e:
            print(f"Error sending heartbeat: {e}")
            return False
    
    def get_peer_status(self, peer_id: str, peer_port: int, heartbeat_timeout: int = 10) -> Dict:
        """Check if a peer is alive based on heartbeat.
        
        Returns dict with:
        - 'alive': bool
        - 'last_seen': datetime or None
        - 'response_time': float or None
        """
        try:
            heartbeat_file = os.path.join(self.temp_dir, f"heartbeat_{peer_port}_{peer_id}.txt")
            
            if not os.path.exists(heartbeat_file):
                return {
                    'alive': False,
                    'last_seen': None,
                    'response_time': None
                }
            
            with open(heartbeat_file, 'r', encoding='utf-8') as f:
                heartbeat_data = json.loads(f.read())
                last_seen = datetime.fromisoformat(heartbeat_data['timestamp'])
                time_since = (datetime.now() - last_seen).total_seconds()
                
                is_alive = time_since < heartbeat_timeout
                
                return {
                    'alive': is_alive,
                    'last_seen': last_seen,
                    'response_time': time_since
                }
        except Exception as e:
            print(f"Error checking peer status for {peer_id}: {e}")
            return {
                'alive': False,
                'last_seen': None,
                'response_time': None
            }
    
    def get_active_peers(self, heartbeat_timeout: int = 10) -> List[Dict]:
        """Get list of all active peers (those sending recent heartbeats).
        
        Returns list of dicts with peer information.
        """
        active_peers = []
        try:
            now = datetime.now()
            for filename in os.listdir(self.temp_dir):
                if filename.startswith("heartbeat_") and filename.endswith(".txt"):
                    try:
                        filepath = os.path.join(self.temp_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            heartbeat_data = json.loads(f.read())
                            last_seen = datetime.fromisoformat(heartbeat_data['timestamp'])
                            time_since = (now - last_seen).total_seconds()
                            
                            if time_since < heartbeat_timeout:
                                active_peers.append({
                                    'user_id': heartbeat_data['user_id'],
                                    'user_port': heartbeat_data['user_port'],
                                    'is_teacher': heartbeat_data.get('is_teacher', False),
                                    'response_time': time_since
                                })
                    except:
                        pass
        except Exception as e:
            print(f"Error discovering active peers: {e}")
        
        return sorted(active_peers, key=lambda x: x['response_time'])
    
    # ==================== RIP ROUTING ====================
    
    def _get_rip_table_file(self) -> str:
        """Get path to RIP routing table file for this peer."""
        return os.path.join(self.temp_dir, f"rip_table_{self.user_port}_{self.user_id}.txt")
    
    def _get_rip_updates_file(self) -> str:
        """Get path to RIP update broadcasts."""
        return os.path.join(self.temp_dir, f"rip_updates_{self.user_port}.txt")
    
    def broadcast_rip_update(self) -> bool:
        """Broadcast RIP routing table update to all peers."""
        try:
            updates_file = self._get_rip_updates_file()
            
            # Build RIP update: destinations we know about and their distances
            rip_update = {
                'sender_id': self.user_id,
                'sender_port': self.user_port,
                'timestamp': datetime.now().isoformat(),
                'routing_table': self.routing_table,
                'msg_id': str(uuid.uuid4())
            }
            
            # Read existing updates
            updates = []
            if os.path.exists(updates_file):
                try:
                    with open(updates_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            for line in content.split('\n'):
                                if line.strip():
                                    try:
                                        updates.append(json.loads(line))
                                    except:
                                        pass
                except:
                    pass
            
            # Add new update
            updates.append(rip_update)
            
            # Keep only recent updates (last hour)
            now = datetime.now()
            updates = [u for u in updates if (now - datetime.fromisoformat(u['timestamp'])).total_seconds() < 3600]
            
            # Write back
            with open(updates_file, 'w', encoding='utf-8') as f:
                for update in updates:
                    f.write(json.dumps(update) + '\n')
            
            return True
        except Exception as e:
            print(f"Error broadcasting RIP update: {e}")
            return False
    
    def process_rip_updates(self) -> bool:
        """Process received RIP updates and update routing table using RIP algorithm.
        
        RIP Algorithm:
        - For each update from neighbor with metric M
        - For each destination D in neighbor's table with cost C
        - New route cost = M + C + 1 (add 1 for link to neighbor)
        - If new route is better than current, update routing table
        """
        try:
            temp_dir = self.temp_dir
            
            # Read from ALL RIP update files (not just our own)
            rip_files = list(__import__('pathlib').Path(temp_dir).glob("rip_updates_*.txt"))
            
            if not rip_files:
                return False
            
            updates_processed = False
            
            for updates_file in rip_files:
                try:
                    with open(updates_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            for line in content.split('\n'):
                                if not line.strip():
                                    continue
                                
                                try:
                                    update = json.loads(line)
                                    sender_id = update['sender_id']
                                    sender_port = update['sender_port']
                                    sender_table = update['routing_table']
                                    
                                    # Skip own updates
                                    if sender_id == self.user_id:
                                        continue
                                    
                                    # Distance to neighbor is 1
                                    neighbor_metric = 1
                                    
                                    # Update route to the sender itself
                                    route_key = f"{sender_id}:{sender_port}"
                                    new_metric = neighbor_metric
                                    
                                    if route_key not in self.routing_table or self.routing_table[route_key][1] > new_metric:
                                        self.routing_table[route_key] = (sender_id, new_metric)
                                        updates_processed = True
                                    
                                    # Update routes through the sender (using sender's routing table)
                                    for dest_key, route_info in sender_table.items():
                                        # Handle both tuple and list formats (JSON converts tuples to lists)
                                        if isinstance(route_info, (tuple, list)) and len(route_info) >= 2:
                                            cost = route_info[1]
                                        else:
                                            continue
                                        
                                        new_metric = neighbor_metric + cost + 1  # RIP metric calculation
                                        
                                        if dest_key not in self.routing_table or self.routing_table[dest_key][1] > new_metric:
                                            self.routing_table[dest_key] = (sender_id, new_metric)
                                            updates_processed = True
                                except:
                                    pass
                except:
                    pass
            
            return updates_processed
        except Exception as e:
            print(f"Error processing RIP updates: {e}")
            return False
    
    def get_route(self, destination_id: str, destination_port: int) -> Optional[Tuple[str, int]]:
        """Get route to destination using RIP routing table.
        
        Returns (next_hop_id, metric) or None if no route exists.
        """
        route_key = f"{destination_id}:{destination_port}"
        return self.routing_table.get(route_key)
    
    def update_routing_metric(self, destination_id: str, destination_port: int, new_metric: int) -> bool:
        """Manually update routing metric for a destination."""
        try:
            route_key = f"{destination_id}:{destination_port}"
            
            if route_key in self.routing_table:
                next_hop, _ = self.routing_table[route_key]
                self.routing_table[route_key] = (next_hop, new_metric)
            else:
                # Direct route (next hop is the destination itself)
                self.routing_table[route_key] = (destination_id, new_metric)
            
            return True
        except Exception as e:
            print(f"Error updating routing metric: {e}")
            return False
    
    def _get_student_registry_file(self) -> str:
        """Get path to student registry file (list of all active students).
        
        Uses a shared registry file (not port-specific) so all students can see each other.
        """
        return os.path.join(self.temp_dir, "student_registry.txt")
    
    def register_student(self) -> bool:
        """Register this student as active (called when student spawns).
        This allows other students to discover them immediately."""
        if self.is_teacher or not self.user_id.startswith("student_"):
            return False
        
        import time
        registry_file = self._get_student_registry_file()
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Read existing students with retry logic
                students = set()
                if os.path.exists(registry_file):
                    try:
                        with open(registry_file, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:
                                students = set(s.strip() for s in content.split('\n') if s.strip())
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(0.1)  # Brief delay before retry
                            continue
                        print(f"Error reading student registry: {e}")
                
                # Add this student
                students.add(self.user_id)
                
                # Write back to file with error handling
                try:
                    with open(registry_file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(sorted(students)))
                    print(f"✓ Student {self.user_id} registered successfully. Registry: {sorted(students)}")
                    return True
                except Exception as write_error:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)  # Brief delay before retry
                        continue
                    print(f"Error writing to registry file: {write_error}")
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1)
                    continue
                print(f"Error registering student: {e}")
                return False
        
        return False
    
    def get_registered_students(self) -> List[str]:
        """Get list of all registered students from the registry file."""
        import time
        registry_file = self._get_student_registry_file()
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if os.path.exists(registry_file):
                    try:
                        with open(registry_file, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:
                                students = [s.strip() for s in content.split('\n') if s.strip()]
                                return sorted(students)
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(0.05)  # Brief delay before retry
                            continue
                        print(f"Error reading student registry: {e}")
                        return []
                else:
                    return []
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.05)
                    continue
                print(f"Error getting registered students: {e}")
                return []
        
        return []
    
    def _get_broadcast_file(self) -> str:
        """Get path to broadcast messages file.
        
        Uses a shared broadcast file (not port-specific) so all users can read/write to same file.
        """
        return os.path.join(self.temp_dir, "broadcast_messages.txt")
    
    def _get_private_file(self, recipient_id: str) -> str:
        """Get path to private message file between two users.
        
        Uses user IDs (not ports) so both parties can access the same file.
        """
        users = sorted([self.user_id, recipient_id])
        filename = f"private_messages_{users[0]}_to_{users[1]}.txt"
        return os.path.join(self.temp_dir, filename)
    
    def send_broadcast(self, message: str) -> str:
        """Send a broadcast message to all users.
        
        Returns message ID for ACK tracking.
        """
        try:
            broadcast_file = self._get_broadcast_file()
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg_id = str(uuid.uuid4())[:8]  # Short message ID
            
            # Read existing messages
            messages = []
            if os.path.exists(broadcast_file):
                try:
                    with open(broadcast_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            messages = content.split('\n')
                except Exception as e:
                    print(f"Error reading broadcast file: {e}")
            
            # Add new message with ID and sender
            formatted_message = f"[{timestamp}] {self.user_id}: {message} (id:{msg_id})"
            messages.append(formatted_message)
            
            # Write back to file
            with open(broadcast_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(messages))
            
            # Track this message for ACK
            self.pending_acks[msg_id] = (datetime.now(), False)
            
            return msg_id
        except Exception as e:
            print(f"Error sending broadcast: {e}")
            return ""
    
    def send_private(self, recipient_id: str, message: str) -> str:
        """Send a private message to a specific user.
        
        Returns message ID for ACK tracking.
        """
        try:
            private_file = self._get_private_file(recipient_id)
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg_id = str(uuid.uuid4())[:8]  # Short message ID
            
            # Read existing messages
            messages = []
            if os.path.exists(private_file):
                try:
                    with open(private_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            messages = content.split('\n')
                except Exception as e:
                    print(f"Error reading private file: {e}")
            
            # Add new message with ID
            formatted_message = f"[{timestamp}] {self.user_id} -> {recipient_id}: {message} (id:{msg_id})"
            messages.append(formatted_message)
            
            # Write back to file
            with open(private_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(messages))
            
            # Track this message for ACK
            self.pending_acks[msg_id] = (datetime.now(), False)
            
            return msg_id
        except Exception as e:
            print(f"Error sending private message: {e}")
            return ""
    
    def get_broadcast_messages(self) -> List[str]:
        """Get all broadcast messages."""
        try:
            broadcast_file = self._get_broadcast_file()
            if os.path.exists(broadcast_file):
                with open(broadcast_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        messages = content.split('\n')
                        return [m for m in messages if m]
            return []
        except Exception as e:
            print(f"Error reading broadcast messages: {e}")
            return []
    
    def get_private_messages(self, other_user_id: str) -> List[str]:
        """Get private messages with another user."""
        try:
            private_file = self._get_private_file(other_user_id)
            if os.path.exists(private_file):
                with open(private_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        messages = content.split('\n')
                        return [m for m in messages if m]
            return []
        except Exception as e:
            print(f"Error reading private messages: {e}")
            return []
    
    def clear_broadcast(self):
        """Clear all broadcast messages."""
        try:
            broadcast_file = self._get_broadcast_file()
            if os.path.exists(broadcast_file):
                os.remove(broadcast_file)
        except Exception as e:
            print(f"Error clearing broadcast messages: {e}")
    
    def clear_private(self, other_user_id: str):
        """Clear private messages with another user."""
        try:
            private_file = self._get_private_file(other_user_id)
            if os.path.exists(private_file):
                os.remove(private_file)
        except Exception as e:
            print(f"Error clearing private messages: {e}")
    
    def get_conversation_partners(self) -> List[str]:
        """Get list of all users this user has conversed with (has private message files with).
        Returns list of user IDs the current user has private messages with."""
        partners = set()
        try:
            temp_dir = self.temp_dir
            
            # Find all private message files for this user
            for filename in os.listdir(temp_dir):
                # Match private message files: private_messages_{user1}_to_{user2}.txt
                if filename.startswith("private_messages_") and filename.endswith(".txt"):
                    # Extract the user IDs from filename
                    parts = filename.replace("private_messages_", "").replace(".txt", "").split("_to_")
                    if len(parts) == 2:
                        user1, user2 = parts[0], parts[1]
                        
                        # Determine which user is not the current user
                        if self.user_id == user1:
                            partners.add(user2)
                        elif self.user_id == user2:
                            partners.add(user1)
        except Exception as e:
            print(f"Error discovering conversation partners: {e}")
        
        return sorted(list(partners))
    
    def get_all_active_students(self) -> List[str]:
        """Get list of all active students in the system by scanning private message files.
        Returns all student IDs (anyone with student_* naming pattern) that have any message files."""
        students = set()
        try:
            temp_dir = self.temp_dir
            
            # Find all private message files (new format: private_messages_{user1}_to_{user2}.txt)
            for filename in os.listdir(temp_dir):
                # Match private message files: private_messages_{user1}_to_{user2}.txt
                if filename.startswith("private_messages_") and filename.endswith(".txt"):
                    # Extract the user IDs from filename
                    parts = filename.replace("private_messages_", "").replace(".txt", "").split("_to_")
                    if len(parts) == 2:
                        user1, user2 = parts[0], parts[1]
                        
                        # Collect all students (anyone with student_* prefix)
                        if user1.startswith("student_"):
                            students.add(user1)
                        if user2.startswith("student_"):
                            students.add(user2)
            
            # Also check broadcast file for student senders
            broadcast_file = self._get_broadcast_file()
            if os.path.exists(broadcast_file):
                try:
                    with open(broadcast_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            for line in content.split('\n'):
                                # Format: [HH:MM:SS] user_id: message
                                if "] " in line:
                                    user_part = line.split("] ")[1].split(":")[0]
                                    if user_part.startswith("student_"):
                                        students.add(user_part)
                except Exception as e:
                    print(f"Error reading broadcast file for students: {e}")
        except Exception as e:
            print(f"Error discovering active students: {e}")
        
        return sorted(list(students))
    
    def get_all_messages(self) -> List[str]:
        """Get all messages (broadcast + private) combined and sorted by timestamp.
        For private messages, only includes those involving the current user."""
        all_messages = []
        
        # Get broadcast messages (visible to everyone)
        broadcast_messages = self.get_broadcast_messages()
        all_messages.extend(broadcast_messages)
        
        # Get only private messages involving this user
        try:
            temp_dir = self.temp_dir
            
            # Find all private message files for this user
            for filename in os.listdir(temp_dir):
                # Match private message files: private_messages_{user1}_to_{user2}.txt
                if filename.startswith("private_messages_") and filename.endswith(".txt"):
                    # Check if current user is in this conversation
                    # File format: private_messages_{user1}_to_{user2}.txt
                    # Extract the user IDs from filename
                    parts = filename.replace("private_messages_", "").replace(".txt", "").split("_to_")
                    if len(parts) == 2:
                        user1, user2 = parts[0], parts[1]
                        
                        # Only include this conversation if current user is one of the participants
                        if self.user_id == user1 or self.user_id == user2:
                            filepath = os.path.join(temp_dir, filename)
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    content = f.read().strip()
                                    if content:
                                        messages = content.split('\n')
                                        all_messages.extend([m for m in messages if m])
                            except Exception as e:
                                print(f"Error reading {filename}: {e}")
        except Exception as e:
            print(f"Error scanning for private messages: {e}")
        
        # Sort messages by timestamp
        try:
            # Extract timestamp from message format: "[HH:MM:SS] user: message"
            def get_timestamp(msg):
                try:
                    # Extract time part between brackets
                    start = msg.find('[') + 1
                    end = msg.find(']')
                    if start > 0 and end > start:
                        time_str = msg[start:end]
                        # Convert to comparable format
                        h, m, s = map(int, time_str.split(':'))
                        return h * 3600 + m * 60 + s
                except:
                    pass
                return 0
            
            all_messages.sort(key=get_timestamp)
        except Exception as e:
            print(f"Error sorting messages: {e}")
        
        return all_messages
    
    # ==================== DELIVERY STATUS & MONITORING ====================
    
    def get_message_delivery_status(self, msg_id: str) -> Dict:
        """Get delivery status of a message.
        
        Returns dict with:
        - 'msg_id': str
        - 'status': 'pending' | 'acknowledged' | 'expired'
        - 'sent_time': datetime
        - 'time_since_sent': float (seconds)
        """
        if msg_id not in self.pending_acks:
            return {
                'msg_id': msg_id,
                'status': 'unknown',
                'sent_time': None,
                'time_since_sent': None
            }
        
        sent_time, acknowledged = self.pending_acks[msg_id]
        time_since = (datetime.now() - sent_time).total_seconds()
        
        if acknowledged or self._check_ack(msg_id):
            status = 'acknowledged'
            self.pending_acks[msg_id] = (sent_time, True)
        elif time_since > 30:  # 30 second timeout
            status = 'expired'
        else:
            status = 'pending'
        
        return {
            'msg_id': msg_id,
            'status': status,
            'sent_time': sent_time,
            'time_since_sent': time_since
        }
    
    def get_system_health(self) -> Dict:
        """Get overall system health metrics.
        
        Returns dict with:
        - 'active_peers': int
        - 'pending_acks': int
        - 'successful_deliveries': int
        - 'failed_deliveries': int
        - 'routing_table_size': int
        - 'average_peer_response_time': float
        """
        active_peers = self.get_active_peers()
        
        # Count delivery statuses
        pending_count = 0
        acked_count = 0
        expired_count = 0
        
        for msg_id in self.pending_acks:
            status = self.get_message_delivery_status(msg_id)['status']
            if status == 'pending':
                pending_count += 1
            elif status == 'acknowledged':
                acked_count += 1
            elif status == 'expired':
                expired_count += 1
        
        # Average response time
        avg_response_time = 0
        if active_peers:
            avg_response_time = sum(p['response_time'] for p in active_peers) / len(active_peers)
        
        return {
            'active_peers': len(active_peers),
            'pending_acks': pending_count,
            'successful_deliveries': acked_count,
            'failed_deliveries': expired_count,
            'routing_table_size': len(self.routing_table),
            'average_peer_response_time': avg_response_time
        }
    
    # ==================== JSON STRUCTURED DATA STORAGE ====================
    
    def _get_json_state_file(self) -> str:
        """Get path to JSON state file for this peer."""
        return os.path.join(self.temp_dir, f"peer_state_{self.user_port}_{self.user_id}.json")
    
    def save_state_to_json(self) -> bool:
        """Save current peer state to JSON file for persistence."""
        try:
            state_file = self._get_json_state_file()
            
            state_data = {
                'user_id': self.user_id,
                'user_port': self.user_port,
                'is_teacher': self.is_teacher,
                'timestamp': datetime.now().isoformat(),
                'pending_acks': {
                    msg_id: {
                        'sent_time': sent_time.isoformat(),
                        'acknowledged': acked
                    }
                    for msg_id, (sent_time, acked) in self.pending_acks.items()
                },
                'routing_table': {
                    dest_key: {'next_hop': next_hop, 'metric': metric}
                    for dest_key, (next_hop, metric) in self.routing_table.items()
                },
                'peer_heartbeats': {
                    peer_id: timestamp.isoformat()
                    for peer_id, timestamp in self.peer_heartbeats.items()
                }
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving state to JSON: {e}")
            return False
    
    def load_state_from_json(self) -> bool:
        """Load peer state from JSON file."""
        try:
            state_file = self._get_json_state_file()
            
            if not os.path.exists(state_file):
                return False
            
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Restore pending ACKs
            self.pending_acks = {}
            for msg_id, ack_info in state_data.get('pending_acks', {}).items():
                sent_time = datetime.fromisoformat(ack_info['sent_time'])
                self.pending_acks[msg_id] = (sent_time, ack_info['acknowledged'])
            
            # Restore routing table
            self.routing_table = {}
            for dest_key, route_info in state_data.get('routing_table', {}).items():
                self.routing_table[dest_key] = (route_info['next_hop'], route_info['metric'])
            
            # Restore peer heartbeats
            self.peer_heartbeats = {}
            for peer_id, timestamp_str in state_data.get('peer_heartbeats', {}).items():
                self.peer_heartbeats[peer_id] = datetime.fromisoformat(timestamp_str)
            
            print(f"✓ Loaded peer state from JSON: {len(self.routing_table)} routes, {len(self.pending_acks)} pending ACKs")
            return True
        except Exception as e:
            print(f"Error loading state from JSON: {e}")
            return False
    
    def export_messages_to_json(self, output_file: Optional[str] = None) -> bool:
        """Export all messages (broadcast + private) to a JSON file for analysis."""
        try:
            if output_file is None:
                output_file = os.path.join(self.temp_dir, f"messages_export_{self.user_port}_{self.user_id}.json")
            
            messages_data = {
                'export_time': datetime.now().isoformat(),
                'user_id': self.user_id,
                'user_port': self.user_port,
                'broadcast_messages': self.get_broadcast_messages(),
                'private_conversations': {},
                'message_summary': {
                    'total_broadcast': len(self.get_broadcast_messages()),
                    'total_partners': len(self.get_conversation_partners())
                }
            }
            
            # Include private conversations
            for partner_id in self.get_conversation_partners():
                messages_data['private_conversations'][partner_id] = self.get_private_messages(partner_id)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(messages_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Messages exported to JSON: {output_file}")
            return True
        except Exception as e:
            print(f"Error exporting messages to JSON: {e}")
            return False
    
    def get_system_state_json(self) -> Dict:
        """Get complete system state as JSON-serializable dictionary."""
        return {
            'peer_info': {
                'user_id': self.user_id,
                'user_port': self.user_port,
                'is_teacher': self.is_teacher,
                'timestamp': datetime.now().isoformat()
            },
            'network_state': self.get_system_health(),
            'routing_state': {
                'routing_table_size': len(self.routing_table),
                'routes': [
                    {
                        'destination': dest_key,
                        'next_hop': next_hop,
                        'metric': metric
                    }
                    for dest_key, (next_hop, metric) in self.routing_table.items()
                ]
            },
            'message_state': {
                'pending_acks': len(self.pending_acks),
                'active_conversations': len(self.get_conversation_partners()),
                'broadcast_count': len(self.get_broadcast_messages())
            }
        }
    
    # ==================== ASYNCIO NON-BLOCKING OPERATIONS ====================
    
    async def async_send_broadcast(self, message: str) -> str:
        """Non-blocking broadcast message sending."""
        return await asyncio.to_thread(self.send_broadcast, message)
    
    async def async_send_private(self, recipient_id: str, message: str) -> str:
        """Non-blocking private message sending."""
        return await asyncio.to_thread(self.send_private, recipient_id, message)
    
    async def async_get_broadcast_messages(self) -> List[Dict]:
        """Non-blocking fetch of broadcast messages."""
        return await asyncio.to_thread(self.get_broadcast_messages)
    
    async def async_get_private_messages(self, partner_id: str) -> List[Dict]:
        """Non-blocking fetch of private messages."""
        return await asyncio.to_thread(self.get_private_messages, partner_id)
    
    async def async_get_active_peers(self) -> List[str]:
        """Non-blocking fetch of active peers."""
        return await asyncio.to_thread(self.get_active_peers)
    
    async def async_save_state_to_json(self) -> bool:
        """Non-blocking state persistence to JSON."""
        return await asyncio.to_thread(self.save_state_to_json)
    
    async def async_load_state_from_json(self) -> bool:
        """Non-blocking state loading from JSON."""
        return await asyncio.to_thread(self.load_state_from_json)
    
    async def async_export_messages_to_json(self, output_file: Optional[str] = None) -> bool:
        """Non-blocking message export to JSON."""
        return await asyncio.to_thread(self.export_messages_to_json, output_file)
    
    async def async_send_heartbeat(self) -> bool:
        """Non-blocking heartbeat sending."""
        return await asyncio.to_thread(self.send_heartbeat)
    
    async def async_get_peer_status(self, peer_id: str) -> str:
        """Non-blocking peer status check."""
        return await asyncio.to_thread(self.get_peer_status, peer_id)
    
    async def async_broadcast_rip_update(self) -> bool:
        """Non-blocking RIP routing update broadcast."""
        return await asyncio.to_thread(self.broadcast_rip_update)
    
    async def async_process_rip_updates(self) -> int:
        """Non-blocking RIP routing update processing."""
        return await asyncio.to_thread(self.process_rip_updates)
    
    async def async_get_system_health(self) -> Dict:
        """Non-blocking system health retrieval."""
        return await asyncio.to_thread(self.get_system_health)
    
    async def async_get_system_state_json(self) -> Dict:
        """Non-blocking system state JSON retrieval."""
        return await asyncio.to_thread(self.get_system_state_json)

