build: clean
	  mkdir -p build
		( \
				python3 -m venv venv; \
				. venv/bin/activate; \
				pip install -r requirements.txt \
		)
	  cp src/* build
	  cp -r ./venv/lib/python3.7/site-packages/* build
		cd build && zip -r9 ../function.zip .

clean:
	  rm -rf build
	  rm -f function.zip

apply: build
	  terraform apply
