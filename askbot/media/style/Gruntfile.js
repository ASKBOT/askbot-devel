module.exports = function(grunt) {

    //Projectconfiguration.
    grunt.initConfig({

        //running`grunt less`willcompileonce
        less: {
            development: {
                options: {
                    paths: ["./"],
		    cleancss: true
                },
                files: {
                    "./style.css": "./style.less"
                }
            }
 },
	// running `grunt watch` will watch for changes
    	watch: {
        	files: "./**/*.less",
        tasks: ["less"]
    }
    });

    //Loadthepluginthatprovidesthe"uglify"task.
    grunt.loadNpmTasks("grunt-contrib-less");
    grunt.loadNpmTasks("grunt-contrib-watch");
 
    //Defaulttask(s).
    grunt.registerTask("default", ["less"]);
};
