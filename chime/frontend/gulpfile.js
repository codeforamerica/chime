var gulp = require('gulp');
var concat = require('gulp-concat');
var del = require('del');

// js
var babel = require('gulp-babel');

// livereload and sync
var browserSync = require('browser-sync').create();

function cleanApp(appFile) {
    return function(cb) {
        del(appFile, cb);
    };
}

function generateApp(options) {
    return function() {
        return gulp.src(options.src)
        .pipe(babel({
            modules: 'amd',
            moduleIds: true,
            sourceRoot: options.sourceRoot,
            moduleRoot: null,
            experimental: 2,
        }))
        .on('error', function (err) { console.error(err.toString()); this.emit('end'); })
        .pipe(concat(options.concat))
        .pipe(gulp.dest(options.dest));
    };
}

function runTasks(opts, done) {
    var source = opts.source;
    var dest = opts.dest;
    var jsRoot = source + '/javascript';

    // output concatenated js files
    var files = {
        js: {
            base: 'base.js',
            shared: 'shared.js',
            activityOverview: 'activity-overview.js',
            articleEdit: 'article-edit.js',
            styleGuide: 'style-guide.js',
        },
    };

    var dir = opts.dir || {
        // input
        js: {
            root: jsRoot,
            base: jsRoot + '/base',
            shared: jsRoot + '/shared',
            activityOverview: jsRoot + '/activity-overview',
            articleEdit: jsRoot + '/article-edit',
            styleGuide: jsRoot + '/styleguide',
        },
        // output
        scripts       : dest + '/javascript/app',
        vendorScripts : dest + '/javascript/vendor',
    };

    var glob = {
        html: opts.glob && opts.glob.html ? opts.glob.html : null,
        js: {
            apps : {},
            lib  : dir.scripts + '/libs.js',
            vendor: [
                source + '/bower_components/stubbyid/stubbyid.js',
                source + '/bower_components/html5shiv/dist/html5shiv.min.js',
                source + '/bower_components/prism/prism.js',
                source + '/bower_components/jquery/dist/jquery.min.js',
            ],
            libs : [
                source + '/bower_components/loader.js/loader.js',
                source + '/node_modules/gulp-babel/node_modules/babel-core/browser-polyfill.js',
                source + '/bower_components/es5-shim/es5-shim.min.js',
                // source + '/bower_components/es5-shim/es5-sham.min.js',
                source + '/bower_components/jquery/dist/jquery.min.js',
                source + '/bower_components/marked/marked.min.js',
                source + '/bower_components/placeholders/placeholders.min.js',
                source + '/bower_components/undo/undo.js',
            ],
        },
    };

    var appNames = [];
    var appName;
    for (appName in files.js) {
        appNames.push(appName);
        glob.js.apps[appName] = dir.js[appName] + '/**/*.js';
    }

    // tasks
    gulp.task('copy', ['copy:vendorjs']);

    gulp.task('copy:vendorjs', function() {
        return gulp.src(glob.js.vendor)
        .pipe(gulp.dest(dir.vendorScripts));
    });

    gulp.task('js:clean', function(cb) {
        del(dir.scripts, cb);
    });

    gulp.task('js:clean:libs', function(cb) {
        del(glob.js.lib, cb);
    });

    for (appName in glob.js.apps) {
        gulp.task('js:clean:' + appName, cleanApp(glob.js.apps[appName]));
    }

    // vendor libraries
    gulp.task('js:libs', ['js:clean:libs'], function() {
        return gulp.src(glob.js.libs)
            .pipe(concat('libs.js'))
            .pipe(gulp.dest(dir.scripts));
    });

    // app source
    gulp.task('js:apps', [
        'js:base',
        'js:shared',
        'js:activityOverview',
        'js:articleEdit',
        'js:styleGuide',
    ]);

    gulp.task('js:base', ['js:clean:base'], generateApp({
        src: [
            glob.js.apps.shared,
            glob.js.apps.base,
        ],
        concat: files.js.base,
        sourceRoot: dir.js.root,
        dest: dir.scripts,
    }));
    gulp.task('js:shared', ['js:clean:shared'], generateApp({
        src: [
            glob.js.apps.shared,
        ],
        concat: files.js.shared,
        sourceRoot: dir.js.root,
        dest: dir.scripts,
    }));
    gulp.task('js:activityOverview', ['js:clean:base'], generateApp({
        src: [
            glob.js.apps.activityOverview,
        ],
        concat: files.js.activityOverview,
        sourceRoot: dir.js.root,
        dest: dir.scripts,
    }));
    gulp.task('js:articleEdit', ['js:clean:base'], generateApp({
        src: [
            glob.js.apps.articleEdit,
        ],
        concat: files.js.articleEdit,
        sourceRoot: dir.js.root,
        dest: dir.scripts,
    }));
    gulp.task('js:styleGuide', ['js:clean:base'], generateApp({
        src: [
            glob.js.apps.styleGuide,
        ],
        concat: files.js.styleGuide,
        sourceRoot: dir.js.root,
        dest: dir.scripts,
    }));

    gulp.task('build', ['js:libs', 'js:apps', 'copy']);

    gulp.task('watch', ['build'], function() {
        // vim hits the filesystem multiple times on saving, so
        // throttling filesystem events helps prevent build errors.
        function throttle(task) {
            return function(event, file) {
                var ev, timer;

                if (!events[event]) {
                    events[event] = {};
                }

                ev = events[event];
                timer = ev[file];

                if (timer) {
                    clearTimeout(timer);
                }

                ev[file] = setTimeout(function () {
                    gulp.start(task, function() {
                        delete ev[file];
                    });
                }, 500);
            };
        }

        var events =  {};
        var i, appName;

        browserSync.init({
            online: false,
            port: 9000,
            proxy: '127.0.0.1:5000',
            ui: {
                port: 8080,
                weinre: {
                    port: 8000,
                },
            },
        });

        for (i = 0; i < appNames.length; i++) {
            appName = appNames[i];
            gulp.watch(glob.js.apps[appName], throttle(['js:' + appName]));
        }

        if (glob.html) {
            gulp.watch(glob.html).on('change', browserSync.reload);
        }
    });

    console.log('apps');
    console.log(files);
    console.log(dir);
    console.log(glob);
    gulp.start('watch');
}

module.exports = runTasks;
