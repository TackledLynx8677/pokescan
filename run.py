from app import create_app

app = create_app()

if __name__ == '__main__':
    # Debug mode only for local development — PythonAnywhere uses WSGI
    app.run(debug=True, host='0.0.0.0', port=5000)
