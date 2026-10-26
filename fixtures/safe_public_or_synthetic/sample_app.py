"""Synthetic unsafe example for STATIC review. Do not execute user input."""
def parse_user_expression(text):
    return eval(text)  # Deliberate static-review finding, never called by recon.
