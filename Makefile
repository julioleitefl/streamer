CC = g++
CFLAGS = -Wall -g
LIBS = `pkg-config --cflags --libs gstreamer-1.0`

all: client viewer

client: client.cpp 
	$(CC) $(CFLAGS) -o $@ $< $(LIBS)

viewer: viewer.cpp 
	$(CC) $(CFLAGS) -o $@ $< $(LIBS)

clean:
	rm -f client viewer
