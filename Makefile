build: clean
	  mkdir -p build
		( \
				. venv/bin/activate \
				pip install -r requirements.txt \
		)
	  cp src/* build
	  cp -r ./venv/lib/python3.7/site-packages/* build
	  zip -r9 function.zip build/

clean:
	  rm -rf build
	  rm -f function.zip

deploy: function.zip
	  terraform apply
