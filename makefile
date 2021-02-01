all: update

update:
	cp ../eelEngine/*.so .

clean:
	rm *.so
