__version__ = '0.1'

import shelve
from os.path import exists, join
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.lang import Builder
from kivy.properties import NumericProperty, ListProperty, ObjectProperty, \
        BooleanProperty
from kivy.utils import get_color_from_hex, boundary
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.uix.stencilview import StencilView
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from functools import partial
from random import randint, random
from time import time

SIZE = 8
LEVEL_TIME = 60
PERCENT_TIMED_JEWEL = 15 / 100.

# 15 -> 12 -> 9.6 -> 7.6 -> 6.4 -> 4.9 ...
DECREASE_TIMED_JEWEL = 0.8

COLORS = map(get_color_from_hex, (
    '#95a5a6', # white
    '#c0392b', # red
    '#d35400', # orange
    '#8e44ad', # purple
    '#f1c40f', # yellow
    '#3498db', # blue
    '#2ecc71', # green
    ))


Builder.load_string('''
<Label>:
    font_name: 'data/coolvetica rg.ttf'

<Jewel>:
    canvas:
        Color:
            rgba: 236 / 255., 240 / 255., 241 / 255., int(self.selected)
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgb: root.color
        Rectangle:
            pos: self.x + 5, self.y + 5
            size: self.width - 10, self.height - 10

<AreaBombJewel>:
    Label:
        pos: root.pos
        size: root.size
        text: 'x'
        font_size: self.height / 2

<LineBombJewel>:
    Label:
        pos: root.pos
        size: root.size
        text: '|'
        font_size: self.height / 2

<TimedJewel>:
    Label:
        pos: root.pos
        size: root.size
        text: '{}'.format(root.time)
        font_size: self.height / 2

<Board>:
    canvas:
        Color:
            rgb: .1, .1, .1
        Rectangle:
            pos: self.pos
            size: self.size

<-SmoothLabel@Label>:
    font_name: 'data/coolvetica rg.ttf'
    canvas:
        Color:
            rgb: 1, 1, 1
        Rectangle:
            pos: self.center_x - self.texture_size[0] / 2., self.center_y - self.texture_size[1] / 2.
            size: self.texture_size
            texture: self.texture

<Timer@Widget>:
    canvas:
        Color:
            rgb: .2, .3, .4
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgb: .8, .8, .9
        Rectangle:
            pos: self.x + dp(4), self.y + dp(4)
            size: sp(50) + (self.width - dp(8) - sp(50)) * app.timer / 60., self.height - dp(8)

    SmoothLabel:
        id: sl
        text: '{}s'.format(int(app.timer))
        font_size: self.height / 1.2
        center_y: root.center_y
        right: root.x + sp(50) + dp(4) + ((root.width - dp(8) - sp(50)) * app.timer / 60.)
        width: '50sp'
        height: root.height - dp(8)
        canvas.before:
            Color:
                rgb: .7, .62, .69
            Rectangle:
                pos: self.pos
                size: self.size
        

<GameOver>:
    canvas:
        Color:
            rgb: .1, .1, .1
        Rectangle:
            size: self.size

    BoxLayout:
        orientation: 'vertical'

        Label:
            text: 'Game Over'
            font_size: '60sp'
            size_hint_y: .25

        BoxLayout:
            Label:
                text: '{}'.format(app.score)
                font_size: '70sp'

            Label:
                text: '1. {}\\n2. {}\\n3. {}\\n'.format(*app.highscores)
                font_size: '40sp'

        Button:
            text: 'Restart'
            font_size: '25sp'
            on_release: app.start()
            size_hint_y: .25

<Sidebar@BoxLayout>:
    canvas:
        Color:
            rgb: .2, .3, .4
        Rectangle:
            pos: self.pos
            size: self.width, self.height * app.timer_next / 60.
            
    Label:
        text: 'Score'
        font_size: '40dp'

    Label:
        text: '{}'.format(app.score)
        font_size: '40dp'

    Widget

    Label:
        text: 'Multiplier'
        font_size: '40dp'

    Label:
        text: '{}x'.format(app.score_multiplier)
        font_size: '40dp'

    Widget

    Label:
        text: 'Combo'
        font_size: '40dp'

    Label:
        text: '{}'.format(app.score_combo)
        font_size: '40dp'

<JewelUI>:
    canvas:
        Color:
            rgb: .1, .1, .1
        Rectangle:
            size: self.size

    BoxLayout:

        Sidebar:
            orientation: 'vertical'
            size_hint_x: None
            width: '200dp'


        BoxLayout:
            orientation: 'vertical'
            padding: '0dp', '5dp'
            Timer:
                size_hint: None, None
                width: board.width
                height: '28dp'
                pos_hint: {'center_x': .5}
            SquareLayout:
                Board:
                    id: board
''')


class Jewel(Widget):
    color = ListProperty([0, 0, 0])
    index = NumericProperty(0)
    ix = NumericProperty(0)
    iy = NumericProperty(0)
    board = ObjectProperty()
    selected = BooleanProperty(False)
    animating = BooleanProperty(False)
    anim = ObjectProperty(None, allownone=True)

    def animate_to(self, x, y, d=0):
        self.animating = True
        if self.anim:
            self.anim.cancel(self)
            self.anim = None

        #distance = Vector(*self.pos).distance(Vector(x, y))
        #distance /= float(self.board.jewel_size)
        #duration = distance * .1
        duration = .20

        anim = Animation(pos=(x, y), d=duration, t='out_sine')
        if d:
            anim = Animation(d=d) + anim
        anim.bind(on_complete=self.on_complete)
        self.anim = anim
        anim.start(self)

    def on_complete(self, *args):
        self.animating = False
        self.board.check(self)

    def stop(self):
        if self.anim:
            self.anim.cancel(self)
            self.anim = None

    def explode(self, *args):
        m = self.board.jewel_size / 2.
        anim = Animation(pos=(self.x + m, self.y + m),
                  size=(1, 1), opacity=0., d=.3)
        anim.bind(on_complete=self.destroy)
        anim.start(self)

    def destroy(self, *args):
        self.board.remove_widget(self)


class TimedJewel(Jewel):
    time = NumericProperty(0)

    def __init__(self, **kwargs):
        self.time = [5, 10][randint(0, 1)]
        super(TimedJewel, self).__init__(**kwargs)

    def explode(self, *args):
        self.board.app.timer_next += self.time
        super(TimedJewel, self).explode(*args)


class AreaBombJewel(Jewel):
    def explode(self, *args):
        super(AreaBombJewel, self).explode(*args)
        ix, iy = self.ix, self.iy
        jewels = []
        for x in range(max(0, ix - 1), min(SIZE, ix + 2)):
            for y in range(max(0, iy - 1), min(SIZE, iy + 2)):
                jewel = self.board.board[x][y]
                if not jewel:
                    continue
                jewels.append(jewel)
        if jewels:
            self.board.bam(jewels, alltogether=True)
            self.board.app.add_score('area', 1 + len(jewels))

class LineBombJewel(Jewel):
    def explode(self, *args):
        super(LineBombJewel, self).explode(*args)
        ix, iy = self.ix, self.iy
        jewels = []
        for x in range(0, SIZE):
            jewel = self.board.board[x][iy]
            if not jewel:
                continue
            jewels.append(jewel)

        for y in range(0, SIZE):
            jewel = self.board.board[ix][y]
            if not jewel:
                continue
            jewels.append(jewel)

        if jewels:
            self.board.bam(jewels, alltogether=True)
            self.board.app.add_score('line', 1 + len(jewels))


class SquareLayout(FloatLayout):
    def do_layout(self, *args):
        s = self.width
        if self.width > self.height:
            s = self.height
        for child in self.children:
            child.size = s, s
            child.center = self.center


class Board(StencilView):

    def __init__(self, **kwargs):
        super(Board, self).__init__(**kwargs)

        self.app = App.get_running_app()
        self.app.board = self
        self.blocked_rows = [0] * SIZE

        # initalize the board
        self.board = []
        for index in range(SIZE):
            self.board += [[None] * SIZE]

        # fill the board
        self.first_fill = True
        Clock.schedule_once(self.fill_board, 1)

        self.bind(pos=self.do_layout, size=self.do_layout)

    def do_layout(self, *args):
        js = self.jewel_size
        for ix in range(SIZE):
            for iy in range(SIZE):
                jewel = self.board[ix][iy]
                if not jewel:
                    continue
                jewel.size = js, js
                jewel.pos = self.index_to_pos(ix, iy)

    def fill_board(self, *args):
        for ix in range(SIZE):
            for iy in range(SIZE):
                jewel = self.board[ix][iy]
                if jewel:
                    continue
                jewel = self.generate()
                jewel.ix = ix
                jewel.iy = iy
                x, y = self.index_to_pos(ix, iy)
                ax, ay = self.index_to_pos(ix, iy + SIZE)
                jewel.pos = ax, ay
                jewel.animate_to(x, y, d=iy / 10. + random() / 10.)
                self.board[ix][iy] = jewel

        self.first_fill = False


    def index_to_pos(self, ix, iy):
        js = self.jewel_size
        return self.x + ix * js, self.y + iy * js

    def touch_to_index(self, tx, ty):
        tx -= self.x
        ty -= self.y
        js = self.jewel_size
        return (
                boundary(0, SIZE, int(tx / js)),
                boundary(0, SIZE, int(ty / js)))

    @property
    def jewel_size(self):
        return int(self.width / SIZE)

    def generate(self):
        index = randint(0, 6)
        color = COLORS[index]
        js = self.jewel_size

        cls = Jewel

        if not self.first_fill:
            if random() < PERCENT_TIMED_JEWEL * pow(
                    DECREASE_TIMED_JEWEL, self.app.score_multiplier):
                cls = TimedJewel

        jewel = cls(index=index, color=color, board=self, size=(js, js))
        self.add_widget(jewel)
        return jewel

    def generate_at(self, ix, iy, cls=Jewel, index=None):
        index = randint(0, 6) if index is None else index
        color = COLORS[index]
        js = self.jewel_size
        jewel = cls(index=index, color=color, board=self, size=(js, js))
        jewel.ix = ix
        jewel.iy = iy
        x, y = self.index_to_pos(ix, iy)
        jewel.pos = x, y
        self.board[ix][iy] = jewel
        self.add_widget(jewel)
        return jewel

    def on_touch_down(self, touch):
        if self.app.no_touch:
            return
        if not self.collide_point(*touch.pos):
            return
        ix, iy = self.touch_to_index(*touch.pos)
        jewel = self.board[ix][iy]
        if not jewel:
            return
        touch.grab(self)
        jewel.selected = True
        touch.ud['source'] = ix, iy
        touch.ud['jewel'] = jewel
        touch.ud['action'] = False

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return
        self.check_touch_swap(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return
        touch.ungrab(self)
        jewel = touch.ud['jewel']
        jewel.selected = False
        self.check_touch_swap(touch)

    def check_touch_swap(self, touch):
        if touch.ud['action']:
            return
        ix, iy = self.touch_to_index(*touch.pos)
        sx, sy = touch.ud['source']

        # index out of bounds ?
        if ix < 0 or ix >= SIZE or iy < 0 or iy >= SIZE:
            return
        # check if we moved
        if ix == iy and sx == sy:
            return

        # we moved, but ensure it's only from "1"
        dx = ix - sx
        dy = iy - sy
        if dx == 0 and dy == 0:
            return

        # try to swap
        ix, iy = ix2, iy2 = touch.ud['source']
        if abs(dx) > abs(dy):
            ix2 += 1 if dx > 0 else -1
        else:
            iy2 += 1 if dy > 0 else -1

        self.swap(ix, iy, ix2, iy2)
        touch.ud['action'] = True

    def swap(self, ix1, iy1, ix2, iy2):
        jewel1 = self.board[ix1][iy1]
        jewel2 = self.board[ix2][iy2]
        if jewel1 is None or jewel2 is None:
            return
        self.board[ix1][iy1] = jewel2
        self.board[ix2][iy2] = jewel1
        jewel1.ix, jewel1.iy = ix2, iy2
        jewel2.ix, jewel2.iy = ix1, iy1

        jewel1.animate_to(*self.index_to_pos(ix2, iy2))
        jewel2.animate_to(*self.index_to_pos(ix1, iy1))

    def check(self, jewel):
        sel_all = []
        sel_x = []
        sel_y = []
        board = self.board
        index = jewel.index
        ix, iy = jewel.ix, jewel.iy

        for x in xrange(ix - 1, -1, -1):
            j = board[x][iy]
            if not j or j.index != index or j.animating:
                break
            sel_all.append(j)
            sel_x.append(j)

        for x in xrange(ix + 1, SIZE):
            j = board[x][iy]
            if not j or j.index != index or j.animating:
                break
            sel_all.append(j)
            sel_x.append(j)

        for y in xrange(iy - 1, -1, -1):
            j = board[ix][y]
            if not j or j.index != index or j.animating:
                break
            sel_all.append(j)
            sel_y.append(j)

        for y in xrange(iy + 1, SIZE):
            j = board[ix][y]
            if not j or j.index != index or j.animating:
                break
            sel_all.append(j)
            sel_y.append(j)

        # counting
        l_all = len(sel_all)
        l_x = len(sel_x)
        l_y = len(sel_y)

        if l_all < 2:
            return
        if l_x < 2 and l_y < 2:
            return

        score_pattern = 'classic'
        score_count = 1

        if l_x >= 2 and l_y >= 2:
            self.bam([jewel] + sel_all)
            score_count += l_all

        elif l_x >= 2:
            self.bam([jewel] + sel_x)
            score_count += l_x
            if l_x == 3:
                score_pattern = '3j'
                self.generate_at(ix, iy, index=jewel.index, cls=AreaBombJewel)
            elif l_x >= 4:
                score_pattern = '4j'
                self.generate_at(ix, iy, index=jewel.index, cls=LineBombJewel)

        elif l_y >= 2:
            self.bam([jewel] + sel_y)
            score_count += l_y
            if l_y == 3:
                score_pattern = '3j'
                self.generate_at(ix, iy, index=jewel.index, cls=AreaBombJewel)
            elif l_y >= 4:
                score_pattern = '4j'
                self.generate_at(ix, iy, index=jewel.index, cls=LineBombJewel)

        self.app.add_score(score_pattern, score_count)


    def bam(self, jewels, alltogether=False):
        # first explode all the jewel
        d = 0
        board = self.board
        rows = []
        for jewel in jewels:
            ix, iy = jewel.ix, jewel.iy
            board[ix][iy] = None
            Clock.schedule_once(jewel.explode, d)
            if not alltogether:
                d += .2
            if ix not in rows:
                rows.append(ix)
                self.blocked_rows[ix] += 1

        if alltogether:
            d = 0.2

        # more combo!
        self.app.score_combo += 1

        Clock.unschedule(self.reset_combo)
        Clock.schedule_once(self.reset_combo, d + 1.)
        Clock.schedule_once(partial(self.unblock_rows, rows), d)

    def unblock_rows(self, rows, *args):
        for row in rows:
            self.blocked_rows[row] -= 1
            if self.blocked_rows[row] == 0:
                self.refill(row)

    def reset_combo(self, *dt):
        self.app.score_combo = 0

    def levelup(self):
        for ix in range(0, SIZE):
            for iy in range(0, SIZE):
                jewel = self.board[ix][iy]
                if not isinstance(jewel, TimedJewel):
                    continue
                self.remove_widget(jewel)
                self.board[ix][iy] = None
                if jewel.time == 5:
                    cls = AreaBombJewel
                else:
                    cls = LineBombJewel
                self.generate_at(ix, iy, index=jewel.index, cls=cls)

    def refill(self, ix):

        # then make them fall down
        board = self.board

        missing = board[ix].count(None)
        if missing == 0:
            return

        row_jewels = [x for x in board[ix] if x is not None]
        board[ix] = [None] * SIZE

        iy = 0
        for jewel in row_jewels:
            if jewel.iy != iy:
                jewel.iy = iy
                jewel.animate_to(*self.index_to_pos(ix, iy))
            board[ix][iy] = jewel
            iy += 1

        for iy in xrange(iy, SIZE):
            jewel = self.generate()
            jewel.ix = ix
            jewel.iy = iy
            x, y = self.index_to_pos(ix, iy)
            ax, ay = self.index_to_pos(ix, iy + missing)
            jewel.pos = ax, ay
            jewel.animate_to(x, y)#, d=(iy - missing) / 10.)
            board[ix][iy] = jewel


class GameOver(Screen):
    pass


class JewelUI(Screen):
    pass


class JewelApp(App):
    score = NumericProperty(0)

    score_multiplier = NumericProperty(1)

    score_combo = NumericProperty(0)

    timer = NumericProperty(LEVEL_TIME)

    timer_next = NumericProperty(0)

    no_touch = BooleanProperty(False)

    highscores = ListProperty([0, 0, 0])

    def build(self):
        self.highscore_fn = join(self.user_data_dir, 'highscore.dat')
        self.root = ScreenManager(transition=SlideTransition())
        self.bind(score_combo=self.check_game_over,
                timer=self.check_game_over,
                timer_next=self.check_game_over)
        self.ui_jewel = JewelUI(name='jewel')
        self.root.add_widget(self.ui_jewel)
        self.start()

        # load highscores
        if not exists(self.highscore_fn):
            return
        d = shelve.open(self.highscore_fn)
        self.highscores = d['scores'][:3]
        d.close()

    def save_highscore(self):
        highscores = self.highscores + [self.score]
        highscores.sort()
        highscores = list(reversed(highscores))[:3]
        self.highscores = highscores
        d = shelve.open(self.highscore_fn)
        d['scores'] = highscores
        d.close()

    def start(self):
        self.score = 0
        self.score_combo = 0
        self.score_multiplier = 1
        self.timer = LEVEL_TIME
        self.start_time = time()
        self.no_touch = False

        self.root.current = 'jewel'

        Clock.schedule_interval(self.update_timer, 1 / 20.)

    def game_over(self):
        self.no_touch = True
        self.timer = 0
        Clock.unschedule(self.update_timer)

    def check_game_over(self, *args):
        if any([self.score_combo, self.timer, self.timer_next]):
            return
        if self.no_touch:
            self.save_highscore()
            if not self.root.has_screen('gameover'):
                self.gameover = GameOver(name='gameover')
                self.root.add_widget(GameOver(name='gameover'))
            self.root.current = 'gameover'

    def update_timer(self, dt):
        self.timer = LEVEL_TIME - (time() - self.start_time)
        if self.timer > 0:
            return

        if self.timer_next == 0:
            self.game_over()
            return

        # next level!
        self.score_multiplier += 1
        self.timer = min(LEVEL_TIME, self.timer_next)
        self.start_time = time()
        self.timer_next = 0
        self.board.levelup()


    def add_score(self, pattern, count):
        m = self.score_multiplier
        score = 0
        if pattern == 'classic':
            score += count * 50
        elif pattern == '4j':
            score += count * 100
        elif pattern == '5j':
            score += count * 150
        elif pattern == '2axes':
            score += count * 200
        elif pattern == 'area':
            score += count * 500
        elif pattern == 'line':
            score += count * 1000

        score *= (1 + self.score_combo)
        self.score += score * m

JewelApp().run()