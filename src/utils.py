from datetime import datetime

def current_greeting():
    hour = datetime.now().hour
    if 7 <= hour < 12:
        return "Good Morning"
    elif 12 <= hour < 17:
        return "Good Afternoon"
    else:
        return "Good Evening"

# Testing block
# if __name__ == "__main__":
#     print(current_greeting())        # Current time ke hisaab se greeting print karega

#     # Optional: manual test for all greetings
#     def test_greeting_at(hour):
#         if 7 <= hour < 12:
#             return "Good Morning"
#         elif 12 <= hour < 17:
#             return "Good Afternoon"
#         else:
#             return "Good Evening"
            
#     print(test_greeting_at(8))   # Good Morning
#     print(test_greeting_at(14))  # Good Afternoon
#     print(test_greeting_at(20))  # Good Evening
