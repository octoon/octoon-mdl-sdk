import os
import shutil

from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
from conan.tools.microsoft import msvc_runtime_flag

required_conan_version = ">=1.35.0"

class MdlConan(ConanFile):
    name = "mdl-sdk"
    license = "Nvidia Source Code License (1-Way Commercial)"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/NVIDIA/MDL-SDK"
    description = "NVIDIA Material Definition Language SDK."
    topics = ("game-development")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": False,
    }

    no_copy_source = True
    short_paths = True

    generators = "cmake"

    requires = "boost/1.73.0", "freeimage/3.18.0", "glew/2.2.0"

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"
    
    @property
    def _is_msvc(self):
        return str(self.settings.compiler) in ["Visual Studio", "msvc"]

    def source(self):
        tools.get(**self.conan_data["sources"][self.version], strip_root=True, destination=self._source_subfolder)

    def export_sources(self):
        self.copy("CMakeLists.txt")

        self.copy("externals/clang/windows/clang.exe")
        self.copy("externals/clang/linux/clang")

        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            self.copy(patch["patch_file"])
        
    def validate(self):
        if self.settings.os not in ["Windows", "Linux", "Macos", "Android", "iOS"]:
            raise ConanInvalidConfiguration("Current os is not supported")

        build_type = self.settings.build_type
        if build_type not in ["Debug", "RelWithDebInfo", "Release"]:
            raise ConanInvalidConfiguration("Current build_type is not supported")

        if self.settings.compiler == "Visual Studio" and tools.Version(self.settings.compiler.version) < 9:
            raise ConanInvalidConfiguration("Visual Studio versions < 9 are not supported")

        if self._is_msvc:
            allowed_runtimes = ["MDd", "MTd"] if build_type == "Debug" else ["MD", "MT"]
            if msvc_runtime_flag(self) not in allowed_runtimes:
                raise ConanInvalidConfiguration(
                    "Visual Studio runtime {0} is required for {1} build type".format(
                        " or ".join(allowed_runtimes),
                        build_type,
                    )
                )

    def _configure_cmake(self):
        cmake = CMake(self)
        cmake.definitions["CMAKE_BUILD_TYPE"]=self.settings.build_type
        cmake.definitions["CMAKE_POSITION_INDEPENDENT_CODE"] = self.options.get_safe("fPIC", False)

        cmake.definitions["MDL_BASE_FOLDER"] = os.path.join(self.build_folder, self._source_subfolder)
        cmake.definitions["MDL_INCLUDE_FOLDER"] = os.path.join(self.build_folder, self._source_subfolder, "include")
        cmake.definitions["MDL_SRC_FOLDER"] = os.path.join(self.build_folder, self._source_subfolder, "src")
        cmake.definitions["MDL_EXAMPLES_FOLDER"] = os.path.join(self.build_folder, self._source_subfolder, "examples")
        cmake.definitions["MDL_BUILD_SDK_EXAMPLES"] = False
        cmake.definitions["MDL_ENABLE_CUDA_EXAMPLES"] = False
        cmake.definitions["MDL_ENABLE_OPENGL_EXAMPLES"] = False
        cmake.definitions["MDL_ENABLE_QT_EXAMPLES"] = False
        cmake.definitions["MDL_ENABLE_D3D12_EXAMPLES"] = False

        if self.settings.os == "Windows":
            cmake.definitions["clang_PATH"] = os.path.join(self.build_folder, "externals/clang/clang.exe")
        else:
            cmake.definitions["clang_PATH"] = os.path.join(self.build_folder, "externals/clang/clang")
        
        freeimage = self.dependencies["freeimage"]
        cmake.definitions["FREEIMAGE_DIR"] = freeimage.package_folder

        cmake.configure(
            build_folder=os.path.join(self.build_folder, self._build_subfolder),
            source_folder=os.path.join(self.build_folder),
        )
        return cmake

    def _copy_sources(self):
        # Copy CMakeLists wrapper
        shutil.copy(os.path.join(self.source_folder, "CMakeLists.txt"), "CMakeLists.txt")

        # Copy patches
        if "patches" in self.conan_data and not os.path.exists("patches"):
            os.mkdir("patches")
        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            shutil.copy(os.path.join(self.source_folder, patch["patch_file"]), "patches")
        
        if not os.path.exists("externals"):
            os.mkdir("externals")
        if not os.path.exists("externals/clang"):
            os.mkdir("externals/clang")
        if self.settings.os == "Windows":
            shutil.copy(os.path.join(self.source_folder, "externals/clang/windows/clang.exe"), "externals/clang/clang.exe")
        elif self.settings.os == "Linux":
            shutil.copy(os.path.join(self.source_folder, "externals/clang/linux/clang.exe"), "externals/clang/clang")
        else:
            shutil.copy(os.path.join(self.source_folder, "externals/clang/linux/clang.exe"), "externals/clang/clang")
        
        # Copy source code
        subfolders_to_copy = [
            "cmake",
            "examples",
            "include",
            "src",
        ]
        for subfolder in subfolders_to_copy:
            shutil.copytree(os.path.join(self.source_folder, self._source_subfolder, subfolder),
                            os.path.join(self._source_subfolder, subfolder))
        
        shutil.copy(os.path.join(self.source_folder, self._source_subfolder, "CMakeLists.txt"),
                            os.path.join(self._source_subfolder, "CMakeLists.txt"))
    
    def _patch_sources(self):
        for patch in self.conan_data["patches"][self.version]:
            tools.patch(**patch)

    def build(self):
        os.environ['GW_DEPS_ROOT'] = os.path.abspath(self._source_subfolder)
        self._copy_sources()
        self._patch_sources()
        cmake = self._configure_cmake()
        cmake.build()

    def _get_build_type(self):
        if self.settings.build_type == "Debug":
            return "debug"
        elif self.settings.build_type == "RelWithDebInfo":
            return "checked"
        elif self.settings.build_type == "Release":
            return "release"
    
    def _get_target_build_platform(self):
        return {
            "Windows" : "windows",
            "Linux" : "linux",
            "Macos" : "mac",
            "Android" : "android",
            "iOS" : "ios"
        }.get(str(self.settings.os))

    def package(self):
        mdl_source_subfolder = os.path.join(self.build_folder, self._source_subfolder)
        mdl_build_subfolder = os.path.join(self.build_folder, self._build_subfolder)

        self.copy(pattern="LICENSE.md", dst="licenses", src=mdl_source_subfolder, keep_path=False)
        self.copy("*.h", dst="include", src=os.path.join(mdl_source_subfolder, "include"))
        self.copy("*.a", dst="lib", src=mdl_build_subfolder, keep_path=False)
        self.copy("*.lib", dst="lib", src=mdl_build_subfolder, keep_path=False)
        self.copy("*.dylib*", dst="lib", src=mdl_build_subfolder, keep_path=False)
        self.copy("*.dll", dst="bin", src=mdl_build_subfolder, keep_path=False)
        self.copy("*.so", dst="lib", src=mdl_build_subfolder, keep_path=False)

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
    
