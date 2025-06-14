import psycopg2
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
connect = psycopg2.connect("dbname=postgres user=postgres password=postgres") # change dbname
cur = connect.cursor()  # create cursor

@app.route('/', methods=['get'])
def login():
    return render_template('login.html', case=0)

@app.route('/', methods=['post'])
def register():
    id = request.form['id']
    password = request.form['password']
    send = request.form['send']

    if send == 'sign in':
        cur.execute("SELECT * FROM users WHERE id = '{}' AND password = '{}'".format(id, password))
        result = cur.fetchall()

        if result:
            return redirect(url_for('main', uid=id))
        else:
            return render_template('login.html', case=1)

    elif send == 'sign up':
        if id.find(' ') == -1 or password.find(' ') == -1:
            return render_template('login.html', case=3)

        cur.execute("SELECT * FROM users WHERE id = '{}'".format(id))
        result = cur.fetchall()

        if result:
            return render_template('login.html', case=2)

        cur.execute("INSERT INTO users VALUES ('{}', '{}', '{}')".format(id, password, 'user'))
        connect.commit()

        return redirect(url_for('main', uid=id))

    else:
        return 'SOMETHING WENT WRONG'

@app.route('/main')
def main():
    uid = request.args['uid']

    mSort, mOrder = request.args.get('mSort', 'rel_date'), request.args.get('mOrder', 'DESC')
    cur.execute('SELECT id, title, TRUNC(AVG(ratings), 1) as ratings, director, genre, rel_date FROM movies \
        LEFT OUTER JOIN reviews ON id = mid GROUP BY id ORDER BY {} {};'.format(mSort, mOrder))
    movies = cur.fetchall()

    rSort, rOrder = request.args.get('rSort', 'rev_time'), request.args.get('rOrder', 'DESC')
    if rSort != 'followers':
        cur.execute('SELECT mid, ratings, uid, title, review, rev_time FROM reviews, movies \
            WHERE mid = id AND uid NOT IN (SELECT id FROM mal_user) ORDER BY {} {};'.format(rSort, rOrder))
    else:
        cur.execute("SELECT mid, ratings, uid, title, review, rev_time FROM reviews, movies \
            WHERE mid = id AND uid IN (SELECT opid FROM ties WHERE id = '{}' AND tie = 'follow') \
            AND uid NOT IN (SELECT id FROM mal_user);".format(uid))
    temp_reviews = cur.fetchall()
    reviews = list(map(lambda review: review[:5] + tuple([review[5].strftime('%Y-%m-%d %H:%M')]), temp_reviews))

    return render_template('main.html', uid=uid, movies=movies, reviews=reviews)

@app.route('/sort-movies', methods=['post'])
def sort_movies():
    uid, value = request.form['uid'], request.form['m-sort']

    if value == 'latest':
        mSort, mOrder = 'rel_date', 'DESC'
    elif value == 'genre':
        mSort, mOrder = 'genre', 'ASC'
    elif value == 'ratings':
        mSort, mOrder = 'ratings', 'DESC'
    else:
        mSort, mOrder = 'WRONG', 'WRONG'

    return redirect(url_for('main', uid=uid, mSort=mSort, mOrder=mOrder))

@app.route('/sort-reviews', methods=['post'])
def sort_reviews():
    uid, value = request.form['uid'], request.form['r-sort']

    if value == 'latest':
        rSort, rOrder = 'rev_time', 'DESC'
    elif value == 'title':
        rSort, rOrder = 'title', 'ASC'
    elif value == 'followers':
        rSort, rOrder = 'followers', 'ASC'
    else:
        rSort, rOrder = 'WRONG', 'WRONG'

    return redirect(url_for('main', uid=uid, rSort=rSort, rOrder=rOrder))

@app.route('/movie-info')
def movie_info():
    uid = request.args['uid']

    cur.execute("SELECT role FROM users where id = '{}';".format(uid))
    uid_role = cur.fetchall()[0][0]

    mid = request.args['mid']
    cur.execute("SELECT id, title, director, genre, rel_date FROM movies WHERE id = '{}';".format(mid))
    movie = cur.fetchall()[0]

    cur.execute("SELECT ratings, uid, review, rev_time FROM reviews WHERE mid = '{}';".format(mid))
    temp_reviews = cur.fetchall()
    reviews = list(map(lambda review: review[:3] + tuple([review[3].strftime('%Y-%m-%d %H:%M')]), temp_reviews))

    cur.execute("SELECT opid FROM ties WHERE id = '{}'".format(uid))
    muted_uids = cur.fetchall()
    muted_uids = [uid for sub_list in muted_uids for uid in sub_list]

    cur.execute("SELECT id FROM mal_user;")
    mal_users = cur.fetchall()
    mal_users = [mal_user for sub_list in mal_users for mal_user in sub_list]

    sum_rating = sum([review[0] for review in reviews])
    avg_rating = round(sum_rating / len(reviews), 1) if sum_rating != 0 else 'None'

    reviews = list(filter(lambda review: (review[1] not in muted_uids) and (review[1] not in mal_users), reviews))

    return render_template('movie-info.html', uid=uid, uid_role=uid_role, movie=movie,
                           reviews=reviews, avg_rating=avg_rating)

@app.route('/movie-info', methods=['post'])
def post_review():
    uid, mid, rating, content = request.form['uid'], request.form['mid'], request.form['rating'], request.form['content']
    cur.execute("SELECT * FROM reviews WHERE uid='{}' AND mid='{}';".format(uid, mid))
    my_review = cur.fetchall()

    if my_review:
        cur.execute("UPDATE reviews SET ratings={}, review='{}', rev_time=NOW()\
            WHERE uid='{}' AND mid='{}';".format(rating, content, uid, mid))
        connect.commit()
    else:
        cur.execute("INSERT INTO reviews VALUES('{}', '{}', {}, '{}', \
            NOW())".format(mid, uid, rating, content))
        connect.commit()

    return redirect(url_for('movie_info', uid=uid, mid=mid))

@app.route('/user-info')
def user_info():
    uid = request.args['uid']

    opid = request.args['opid']
    cur.execute("SELECT mid, ratings, title, review, rev_time FROM reviews, movies \
        WHERE mid = id AND uid = '{}';".format(opid))
    temp_reviews = cur.fetchall()
    reviews = list(map(lambda review: review[:4] + tuple([review[4].strftime('%Y-%m-%d %H:%M')]), temp_reviews))

    cur.execute("SELECT id FROM ties WHERE tie = 'follow' AND opid = '{}' \
        AND id NOT IN (SELECT id FROM mal_user);".format(opid))
    followers = cur.fetchall()  # users who follow opid user
    followers = [follower for sub_list in followers for follower in sub_list]

    cur.execute("SELECT role FROM users where id = '{}';".format(uid))
    uid_role = cur.fetchall()[0][0]

    cur.execute("SELECT role FROM users where id = '{}';".format(opid))
    opid_role = cur.fetchall()[0][0]

    if uid == opid:
        if uid_role == 'admin':
            cur.execute("SELECT id FROM mal_user")
            mal_users = cur.fetchall()
            mal_users = [mal_user for sub_list in mal_users for mal_user in sub_list]

            return render_template('user-info.html', uid=uid, opid=opid, reviews=reviews, followers=followers,
                                   uid_role=uid_role, mal_users=mal_users)
        else:
            cur.execute("SELECT opid FROM ties WHERE id = '{}' AND tie = 'follow' \
                AND opid NOT IN (SELECT id FROM mal_user);".format(uid))
            followed_users = cur.fetchall()  # users that I(uid user) followed
            followed_users = [followed_user for sub_list in followed_users for followed_user in sub_list]

            cur.execute("SELECT opid FROM ties WHERE id = '{}' AND tie = 'mute'\
                AND opid NOT IN (SELECT id FROM mal_user);".format(uid))
            muted_users = cur.fetchall()  # users that I(uid user) muted
            muted_users = [muted_user for sub_list in muted_users for muted_user in sub_list]

            return render_template('user-info.html', uid=uid, opid=opid, reviews=reviews, followers=followers,
                               followed_users=followed_users, muted_users=muted_users, uid_role=uid_role)
    else:
        return render_template('user-info.html', uid=uid, opid=opid, reviews=reviews, followers=followers,
                               uid_role=uid_role, opid_role=opid_role)

@app.route('/tie-user') # maybe method post?
def tie_user():
    uid = request.args['uid']
    opid = request.args['opid']
    action = request.args['action']

    cur.execute("SELECT opid FROM ties WHERE id = '{}' AND tie = 'follow';".format(uid))
    followed_users = cur.fetchall()  # users that I(uid user) followed
    followed_users = [followed_user for sub_list in followed_users for followed_user in sub_list]

    cur.execute("SELECT opid FROM ties WHERE id = '{}' AND tie = 'mute';".format(uid))
    muted_users = cur.fetchall()  # users that I(uid user) muted
    muted_users = [muted_user for sub_list in muted_users for muted_user in sub_list]

    if action == 'follow':
        if opid in muted_users:
            cur.execute("DELETE FROM ties WHERE id = '{}' AND opid = '{}' AND tie = 'mute';".format(uid, opid))
            connect.commit()
        if opid not in followed_users:
            cur.execute("INSERT INTO ties VALUES ('{}', '{}', 'follow')".format(uid, opid))
            connect.commit()

    else:
        if opid in followed_users:
            cur.execute("DELETE FROM ties WHERE id = '{}' AND opid = '{}' AND tie = 'follow';".format(uid, opid))
            connect.commit()
        if opid not in muted_users:
            cur.execute("INSERT INTO ties VALUES ('{}', '{}', 'mute')".format(uid, opid))
            connect.commit()
    return redirect(url_for('user_info', uid=uid, opid=opid))

@app.route('/untie-user') # maybe method post?
def untie_user(): # when uid is watching uid's page
    uid = request.args['uid']
    opid = request.args['opid']
    action = request.args['action']

    if action == 'unfollow':
        cur.execute("SELECT opid FROM ties WHERE id = '{}' AND tie = 'follow';".format(uid))
        followed_users = cur.fetchall()  # users that I(uid user) followed
        followed_users = [followed_user for sub_list in followed_users for followed_user in sub_list]

        if opid in followed_users:
            cur.execute("DELETE FROM ties WHERE id = '{}' AND opid = '{}' AND tie = 'follow';".format(uid, opid))
            connect.commit()

    else:
        cur.execute("SELECT opid FROM ties WHERE id = '{}' AND tie = 'mute';".format(uid))
        muted_users = cur.fetchall()  # users that I(uid user) muted
        muted_users = [muted_user for sub_list in muted_users for muted_user in sub_list]

        if opid in muted_users:
            cur.execute("DELETE FROM ties WHERE id = '{}' AND opid = '{}' AND tie = 'mute';".format(uid, opid))
            connect.commit()

    return redirect(url_for('user_info', uid=uid, opid=uid))

@app.route('/add-movie', methods=['post'])
def add_movie():
    uid = request.form['uid']
    opid = request.form['opid']

    title, director, genre, rel_date = (
        request.form['title'], request.form['director'], request.form['genre'], request.form['rel_date'])

    cur.execute("SELECT MAX(id) FROM movies")
    max_id = int(cur.fetchall()[0][0])

    cur.execute("INSERT INTO movies VALUES \
        ('{}', '{}', '{}', '{}', '{}');".format(max_id + 1, title, director, genre, rel_date))

    connect.commit()

    return redirect((url_for('user_info', uid=uid, opid=opid)))

@app.route('/delete-review', methods=['post'])
def delete_review():
    uid = request.form['uid']
    opid = request.form['opid']
    mid = request.form['mid']

    cur.execute("DELETE FROM reviews WHERE mid = '{}' and uid = '{}';".format(mid, opid))
    connect.commit()

    return redirect(url_for('user_info', uid=uid, opid=opid))

@app.route('/delete-movie', methods=['post'])
def delete_movie():
    uid = request.form['uid']
    mid = request.form['mid']

    cur.execute("DELETE FROM reviews WHERE mid = '{}'".format(mid))
    connect.commit()
    cur.execute("DELETE FROM movies WHERE id = '{}'".format(mid))
    connect.commit()

    return redirect(url_for('main', uid=uid))

@app.route('/mal-user')
def mal_user():
    uid = request.args['uid']
    mal_user = request.args['mal_user']
    action = request.args['action']

    if action == 'unset':
        cur.execute("DELETE FROM mal_user WHERE id = '{}';".format(mal_user))
        connect.commit()
    else:
        cur.execute("SELECT * FROM users WHERE id = '{}';".format(mal_user))
        exists = cur.fetchall()

        if exists:
            cur.execute("INSERT INTO mal_user VALUES ('{}', NOW());".format(mal_user))
            connect.commit()

    return redirect(url_for('user_info', uid=uid, opid=uid))


if __name__ == '__main__':
    app.run(debug=True)
