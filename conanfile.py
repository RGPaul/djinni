from conan import ConanFile
from conan.errors import ConanException
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import to_apple_arch
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
from conan.tools.files import save, load, copy, collect_libs
from conan.tools.gnu import AutotoolsToolchain, AutotoolsDeps
from shutil import copy2
import os

class DjinniConan(ConanFile):
    name = "djinni"
    version = "470"
    author = "Ralph-Gordon Paul (development@rgpaul.com)"
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "android_ndk": [None, "ANY"], 
        "android_stl_type":["c++_static", "c++_shared"]}
    default_options = {"shared": False, "android_ndk": None, "android_stl_type": "c++_static"}
    description = "A tool for generating cross-language type declarations and interface bindings."
    url = "https://github.com/RGPaul/djinni"
    license = "Apache-2.0"
    exports_sources = "CMakeLists.txt", "src/*", "include/*", "extension-libs/*", "support-lib/*", "bin/djinni.jar"
    generators = "CMakeDeps"

    def generate(self):
        tc = CMakeToolchain(self)

        if self.settings.os == "Android":
            android_toolchain = os.environ["ANDROID_NDK_PATH"] + "/build/cmake/android.toolchain.cmake"
            tc.variables["CMAKE_SYSTEM_NAME"] = "Android"
            tc.variables["CMAKE_TOOLCHAIN_FILE"] = android_toolchain
            tc.variables["ANDROID_NDK"] = os.environ["ANDROID_NDK_PATH"]
            tc.variables["ANDROID_ABI"] = tools.to_android_abi(self.settings.arch)
            tc.variables["ANDROID_STL"] = self.options.android_stl_type
            tc.variables["ANDROID_NATIVE_API_LEVEL"] = self.settings.os.api_level
            tc.variables["ANDROID_TOOLCHAIN"] = "clang"
            tc.cache_variables["DJINNI_WITH_JNI"] = True

        if self.settings.os == "iOS":
            tc.cache_variables["CMAKE_SYSTEM_NAME"] = "iOS"
            tc.cache_variables["CMAKE_OSX_DEPLOYMENT_TARGET"] = "10.0"
            tc.cache_variables["CMAKE_XCODE_ATTRIBUTE_ONLY_ACTIVE_ARCH"] = False
            tc.cache_variables["CMAKE_IOS_INSTALL_COMBINED"] = True
            tc.cache_variables["CMAKE_OSX_SYSROOT"] = "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk"
            tc.cache_variables["DJINNI_WITH_OBJC"] = True

            # define all architectures for ios fat library
            if "arm" in self.settings.arch:
                tc.cache_variables["CMAKE_OSX_ARCHITECTURES"] = "armv7;armv7s;arm64;arm64e"
            else:
                tc.cache_variables["CMAKE_OSX_ARCHITECTURES"] = to_apple_arch(self)

        if self.settings.os == "Macos":
            tc.cache_variables["DJINNI_WITH_OBJC"] = True
            tc.cache_variables["CMAKE_OSX_ARCHITECTURES"] = to_apple_arch(self)

        if self.options.shared == False:
            tc.cache_variables["DJINNI_STATIC_LIB"] = True

        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.verbose = True
        cmake.configure()
        cmake.build()

        # we have to create the include structure ourself, because there is no install in the djinni cmakelists
        include_folder = os.path.join(self.build_folder, "include")
        os.mkdir(include_folder)
        include_djinni_folder = os.path.join(include_folder, "djinni")
        os.mkdir(include_djinni_folder)

        # copy common support lib headers
        support_lib_folder = os.path.join(self.source_folder, "support-lib")
        for f in os.listdir(support_lib_folder):
            if f.endswith(".hpp") and not os.path.islink(os.path.join(support_lib_folder,f)):
                copy2(os.path.join(support_lib_folder,f), os.path.join(include_djinni_folder,f))

        # copy objc specific header files
        if self.settings.os == "iOS":
            include_objc_folder = os.path.join(include_djinni_folder, "objc")
            os.mkdir(include_objc_folder)
            support_lib_objc_folder = os.path.join(support_lib_folder, "objc")
            for f in os.listdir(support_lib_objc_folder):
                if f.endswith(".h") and not os.path.islink(os.path.join(support_lib_objc_folder,f)):
                    copy2(os.path.join(support_lib_objc_folder,f), os.path.join(include_objc_folder,f))

        # copy jni specific header files
        if self.settings.os == "Android":
            include_jni_folder = os.path.join(include_djinni_folder, "jni")
            os.mkdir(include_jni_folder)
            support_lib_jni_folder = os.path.join(support_lib_folder, "jni")
            for f in os.listdir(support_lib_jni_folder):
                if f.endswith(".hpp") and not os.path.islink(os.path.join(support_lib_jni_folder,f)):
                    copy2(os.path.join(support_lib_jni_folder,f), os.path.join(include_jni_folder,f))        

    def package(self):
        copy(self, "*", os.path.join(self.build_folder, "include"), os.path.join(self.package_folder, "include"), keep_path=True)
        copy(self, "*.lib", self.build_folder, os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.dll", self.build_folder, os.path.join(self.package_folder, "bin"), keep_path=False)
        copy(self, "*.so", self.build_folder, os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.dylib", self.build_folder, os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.a", self.build_folder, os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "djinni.jar", os.path.join(self.source_folder, "bin"), os.path.join(self.package_folder, "bin"), keep_path=False)
            
    def package_info(self):
        self.cpp_info.libs = collect_libs(self)
        self.cpp_info.includedirs = ['include']

    def package_id(self):
        if "arm" in self.info.settings.get_safe("arch") and self.info.settings.get_safe("os") == "iOS":
            self.info.settings.arch = "AnyARM"

    def config_options(self):
        # remove android specific option for all other platforms
        if self.settings.os != "Android":
            del self.options.android_ndk
            del self.options.android_stl_type
    
    def layout(self):
        cmake_layout(self)
