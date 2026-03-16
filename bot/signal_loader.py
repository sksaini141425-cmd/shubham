import json
import re
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SignalLoader:
    def __init__(self, signals_file=r'C:\Users\sksai\vip_signals.json'):
        self.signals_file = signals_file
        self.last_parsed_timestamp = datetime.now() - timedelta(minutes=60) # Only look at recent signals
        
    def get_new_signals(self, window_minutes=15):
        """
        Scans the JSON for signals posted within the last X minutes.
        """
        if not os.path.exists(self.signals_file):
            return []
            
        try:
            with open(self.signals_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading signals file: {e}")
            return []

        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        new_signals = []
        
        # In a real scenario, we'd only look at the most recent entries.
        # Since the file might be large, we'll iterate backwards or just take the top items.
        for item in data[:50]: # Check the latest 50 messages
            try:
                date_str = item.get('date', '').replace('Z', '+00:00')
                msg_date = datetime.fromisoformat(date_str)
                
                if msg_date > cutoff:
                    parsed = self._parse_signal_text(item.get('text', ''), item.get('group', ''))
                    if parsed:
                        parsed['original_date'] = date_str
                        new_signals.append(parsed)
            except Exception as e:
                continue
                
        return new_signals

    def _parse_signal_text(self, text, group=""):
        # Clean text for easier parsing
        clean_text = text.replace('**', '').replace('__', '').replace('*', '')
        clean_text = re.sub(r'[🔴📉💠✔🟣🔟⚡✅💠💠💠]', ' ', clean_text)
        
        if not any(x in clean_text.upper() for x in ['STOP', 'LOSS', 'PROFIT', 'TARGET', 'TAKE']):
            return None

        # Extract Provider
        provider = "Unknown"
        provider_match = re.search(r'by (.*?) trader', clean_text, re.IGNORECASE)
        if provider_match:
            provider = provider_match.group(1).strip()
        elif "O'Brien" in group:
            provider = "O'Brien"

        # Extract Symbol
        symbol = None
        sym_match = re.search(r'([A-Z0-9]{2,10})/?USDT', clean_text.upper())
        if sym_match:
            symbol = f"{sym_match.group(1)}USDT"
        
        if not symbol:
            sym_match = re.search(r'#([A-Z0-9]{2,10})', clean_text.upper())
            if sym_match:
                symbol = f"{sym_match.group(1)}USDT"
        
        if not symbol: return None

        # Extract Side
        side = None
        if 'LONG' in clean_text.upper() or 'BUY' in clean_text.upper():
            side = 'LONG'
        if 'SHORT' in clean_text.upper() or 'SELL' in clean_text.upper():
            side = 'SHORT'
        
        if not side: return None

        # Extract Entry, TP, SL
        entry = None
        tp = None
        sl = None
        
        lines = [line.strip().upper() for line in clean_text.split('\n') if line.strip()]
        for line in lines:
            nums = re.findall(r'\d+(?:\.\d+)?', line.replace('$', ''))
            if not nums: continue
            val = float(nums[0])
            
            if any(x in line for x in ['BUY', 'ENTRY', 'NOW']):
                if not entry: entry = val
            elif any(x in line for x in ['STOP', 'SL']):
                if not sl: sl = val
            elif any(x in line for x in ['PROFIT', 'TARGET', 'TP']):
                if not tp: tp = val
                
        if not all([entry, tp, sl]):
            return None

        return {
            'provider': provider,
            'symbol': symbol,
            'side': side,
            'entry': entry,
            'tp': tp,
            'sl': sl
        }
