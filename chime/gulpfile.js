var gulp = require('gulp');

var frontendDir = './frontend';

gulp.task('default', function(done) {
    require(frontendDir + '/gulpfile.js')({
        source: frontendDir,
        dest: './static',
        glob: {
            html: 'templates/**/*.html',
        },
    }, done);
});
