#----------------------------------------------------------------
# Generated CMake target import file for configuration "RelWithDebInfo".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "RdKafka::rdkafka" for configuration "RelWithDebInfo"
set_property(TARGET RdKafka::rdkafka APPEND PROPERTY IMPORTED_CONFIGURATIONS RELWITHDEBINFO)
set_target_properties(RdKafka::rdkafka PROPERTIES
  IMPORTED_IMPLIB_RELWITHDEBINFO "${_IMPORT_PREFIX}/lib/rdkafka.lib"
  IMPORTED_LOCATION_RELWITHDEBINFO "${_IMPORT_PREFIX}/bin/rdkafka.dll"
  )

list(APPEND _cmake_import_check_targets RdKafka::rdkafka )
list(APPEND _cmake_import_check_files_for_RdKafka::rdkafka "${_IMPORT_PREFIX}/lib/rdkafka.lib" "${_IMPORT_PREFIX}/bin/rdkafka.dll" )

# Import target "RdKafka::rdkafka++" for configuration "RelWithDebInfo"
set_property(TARGET RdKafka::rdkafka++ APPEND PROPERTY IMPORTED_CONFIGURATIONS RELWITHDEBINFO)
set_target_properties(RdKafka::rdkafka++ PROPERTIES
  IMPORTED_IMPLIB_RELWITHDEBINFO "${_IMPORT_PREFIX}/lib/rdkafka++.lib"
  IMPORTED_LOCATION_RELWITHDEBINFO "${_IMPORT_PREFIX}/bin/rdkafka++.dll"
  )

list(APPEND _cmake_import_check_targets RdKafka::rdkafka++ )
list(APPEND _cmake_import_check_files_for_RdKafka::rdkafka++ "${_IMPORT_PREFIX}/lib/rdkafka++.lib" "${_IMPORT_PREFIX}/bin/rdkafka++.dll" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
