import shlex

configs = [
    r'--psm 7 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "',
    r"--psm 7 -c tessedit_char_whitelist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '",
    r'--psm 7 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"',  # No space
    r'--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',   # No quotes no space
]

print("Testing shlex.split on configs:")
for i, c in enumerate(configs):
    print(f"--- Config {i} ---")
    print(f"Raw: >{c}<")
    try:
        parts = shlex.split(c)
        print(f"Parsed: {parts}")
    except ValueError as e:
        print(f"Error: {e}")
