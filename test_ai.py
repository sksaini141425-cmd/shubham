from bot.ai_brain import AIBrain

brain = AIBrain(api_key='AIzaSyDa6_XPP2Gk_iNImqHAVZ2dGRqUuLnyVqo')

try:
    print("Test 1: Hello")
    reply1 = brain.generate_reply("Hello! Can you hear me?", context="Scanning 20 markets. No open positions.", chat_id="test123")
    print("Reply 1:", reply1)

    print("\nTest 2: Memory check")
    reply2 = brain.generate_reply("What did I just say?", context="Scanning 20 markets. No open positions.", chat_id="test123")
    print("Reply 2:", reply2)
except Exception as e:
    import traceback
    traceback.print_exc()
