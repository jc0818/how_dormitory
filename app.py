from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # 사용자 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    # 게시글 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT NOT NULL
        )
    ''')
    # 댓글 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            author TEXT NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    ''')
    # 기숙사 평점 테이블 생성, date 컬럼 추가
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dormitory_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dormitory_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            reviewer TEXT NOT NULL,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

    

init_db()


@app.route('/dormitory_rating', methods=['GET', 'POST'])
def dormitory_rating():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        dormitory_name = request.form['dormitory_name']
        rating = int(request.form['rating'])
        reviewer = session['username']
        current_date = datetime.now().date()

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # 한 달 이내에 같은 기숙사에 평점을 남겼는지 확인
        cursor.execute('''
            SELECT date FROM dormitory_ratings
            WHERE dormitory_name = ? AND reviewer = ?
            ORDER BY date DESC LIMIT 1
        ''', (dormitory_name, reviewer))
        last_rating_date = cursor.fetchone()

        # 사용자가 이전에 평점을 남긴 경우에만 날짜 확인
        if last_rating_date and last_rating_date[0] is not None:
            last_rating_date = datetime.strptime(last_rating_date[0], '%Y-%m-%d').date()
            if current_date <= last_rating_date + timedelta(days=30):
                flash('한 달에 한 번만 평점을 남길 수 있습니다.', 'error')
                conn.close()
                return redirect(url_for('dormitory_rating'))

        # 평점 저장
        cursor.execute('INSERT INTO dormitory_ratings (dormitory_name, rating, reviewer, date) VALUES (?, ?, ?, ?)', 
                       (dormitory_name, rating, reviewer, current_date.strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()

        flash(f'{dormitory_name}에 대한 별점이 성공적으로 추가되었습니다!', 'success')
        return redirect(url_for('dormitory_rating'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT dormitory_name, AVG(rating) FROM dormitory_ratings GROUP BY dormitory_name')
    ratings = cursor.fetchall()
    conn.close()

    return render_template('dormitory_rating.html', ratings=ratings)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])#디폴트 값 sha256 암호화

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            
            return redirect(url_for('login'))  
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            session['username'] = username
            return redirect(url_for('home'))
        
           

    return render_template('login.html')
@app.route('/')
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'username' not in session:
        return redirect(url_for('login'))

    # 해당 검색어에 맞는 게시글
    query = request.args.get('query')
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if query:
        # 제목에 검색어가 포함된 게시글을 검색
        cursor.execute('SELECT id, title, content, author FROM posts WHERE title LIKE ?', ('%' + query + '%',))
    else:
        # 검색내용 없으면 모든 게시글 출력
        cursor.execute('SELECT id, title, content, author FROM posts')
    
    posts = cursor.fetchall()
    conn.close()

    return render_template('home.html', username=session['username'], posts=posts, query=query)


@app.route('/search', methods=['GET'])
def search():
    # 검색어를 쿼리 파라미터로 받기
    query = request.args.get('query', '')

    if not query:
        return redirect(url_for('home'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # 제목에 검색어가 포함된 게시글을 검색
    cursor.execute('SELECT id, title, content, author FROM posts WHERE title LIKE ?', ('%' + query + '%',))
    posts = cursor.fetchall()
    conn.close()

    return render_template('search_results.html', query=query, posts=posts)

@app.route('/post', methods=['GET', 'POST'])
def post():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author = session['username']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO posts (title, content, author) VALUES (?, ?, ?)', (title, content, author))
        conn.commit()
        conn.close()

        return redirect(url_for('home'))

    return render_template('post.html')

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT title, content, author FROM posts WHERE id = ?', (post_id,))
    post = cursor.fetchone()

    if request.method == 'POST':
        comment_content = request.form['content']
        comment_author = session['username']
        cursor.execute('INSERT INTO comments (post_id, content, author) VALUES (?, ?, ?)', 
                       (post_id, comment_content, comment_author))
        conn.commit()
        
    
    cursor.execute('SELECT content, author FROM comments WHERE post_id = ?', (post_id,))
    comments = cursor.fetchall()
    conn.close()
    
    return render_template('post_detail.html', post=post, comments=comments, post_id=post_id)

@app.route('/logout')
def logout():
    session.pop('username', None)
    
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
