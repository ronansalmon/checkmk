cmake_minimum_required(VERSION 3.20)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_VERBOSE_MAKEFILE ON)
set(PLANTUTML_VERSION 1.2022.13)
set(CMAKE_CXX_COMPILER g++-12) # TODO: replace with more intelligent approach

project(
  Livestatus
  VERSION 0.1
  DESCRIPTION "Livestatus library"
  LANGUAGES CXX)

add_subdirectory(src)
add_subdirectory(test)
add_subdirectory(doc)
