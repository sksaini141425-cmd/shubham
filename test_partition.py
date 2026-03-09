from bot.data_loader import DataLoader
import logging

logging.basicConfig(level=logging.INFO)

dl = DataLoader()
print("--- Set 1 (Offset 0, Limit 5) ---")
set1 = dl.get_top_futures_symbols(top_n=5, offset=0)
print(set1)

print("\n--- Set 2 (Offset 5, Limit 5) ---")
set2 = dl.get_top_futures_symbols(top_n=5, offset=5)
print(set2)

overlap = set(set1).intersection(set(set2))
if not overlap and len(set1) == 5 and len(set2) == 5:
    print("\n✅ Verification Successful: No overlap between sets.")
else:
    print(f"\n❌ Verification Failed: Overlap found: {overlap}")
