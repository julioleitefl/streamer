import sys
from dynamic_streamer import DynamicStreamer

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 start_dynamic_streamer.py <input_uri_auth> <output_uri_auth> <output_uri_auth_web>")
        sys.exit(1)

    input_uri_auth = sys.argv[1]
    output_uri_auth = sys.argv[2]
    output_uri_auth_web = sys.argv[3]

    streamer = DynamicStreamer(input_uri_auth, output_uri_auth, output_uri_auth_web)
    streamer.start_streaming()
